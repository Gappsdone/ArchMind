"""ArchMind command line interface."""

import json
import os
from pathlib import Path

import typer

from .core import Store

app = typer.Typer(help="ArchMind — local CMake architecture intelligence")
project_app = typer.Typer()
app.add_typer(project_app, name="project")


def store() -> Store:
    return Store(Path(os.getenv("ARCHMIND_DB", "archmind.db")))


def output(value):
    typer.echo(json.dumps(value, indent=2))


@project_app.command("add")
def project_add(name: str = typer.Option(...), root: Path = typer.Option(...)):
    output(store().project_add(name, root))


@app.command()
def analyze(
    project: str = typer.Option(...),
    build_dir: Path = typer.Option(...),
    config: str = typer.Option(""),
    configure: bool = typer.Option(False),
    semantic: bool = typer.Option(False, help="Also index C++ classes with clang-uml"),
    generator: str | None = typer.Option(None, help="CMake generator for --configure"),
):
    analyzers = ("cmake", "clang-uml") if semantic else ("cmake",)
    output(
        store().analyze(
            project, build_dir, config, configure, analyzers=analyzers, generator=generator
        )
    )


@app.command()
def targets(snapshot: str = typer.Option(...)):
    db = store()
    cursor = None
    items = []
    while True:
        page = db.nodes(snapshot, kind="CMAKE_TARGET", cursor=cursor, limit=500)
        items.extend(page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    output({"items": items})


@app.command()
def dependencies(
    snapshot: str = typer.Option(...),
    target: str = typer.Option(...),
    reverse: bool = typer.Option(False),
    kind: str = typer.Option("BUILD_DEPENDS_ON"),
):
    db = store()
    node = db.node_by_key(snapshot, target)
    if node["kind"] != "CMAKE_TARGET":
        raise typer.BadParameter(f"Not a CMake target: {target}")
    output(
        db.edges(
            snapshot,
            target_id=node["id"] if reverse else None,
            source_id=None if reverse else node["id"],
            kind=kind,
        )
    )


@app.command()
def cycles(snapshot: str = typer.Option(...), kind: str = typer.Option("BUILD_DEPENDS_ON")):
    output(store().cycles(snapshot, kind))


@app.command()
def evidence(snapshot: str = typer.Option(...), edge: str = typer.Option(...)):
    output(store().evidence(snapshot, edge))


@app.command()
def symbols(snapshot: str = typer.Option(...), target: str = typer.Option(...)):
    db = store()
    node = db.node_by_key(snapshot, target)
    output(db.target_symbols(snapshot, node["id"]))


@app.command()
def impact(
    snapshot: str = typer.Option(...), symbol: str = typer.Option(...), depth: int = typer.Option(2)
):
    db = store()
    node = db.node_by_key(snapshot, symbol)
    output(db.impact(snapshot, node["id"], depth))


@app.command()
def trace(snapshot: str = typer.Option(...), edge: str = typer.Option(...)):
    output(store().symbol_trace(snapshot, edge))


@app.command("mcp")
def mcp_serve():
    """Serve read-only architecture tools over local MCP stdio."""
    from .mcp_server import create_mcp_server

    create_mcp_server().run(transport="stdio")


@app.command()
def serve(host: str = typer.Option("127.0.0.1"), port: int = typer.Option(8000)):
    import uvicorn

    uvicorn.run("archmind.api:create_app", factory=True, host=host, port=port)


if __name__ == "__main__":
    app()
