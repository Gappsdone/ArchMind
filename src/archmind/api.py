"""Loopback-first versioned REST API."""

import json
import logging
import os
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from .core import NotFound, Store

logger = logging.getLogger(__name__)


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    root_path: str


class AnalysisInput(BaseModel):
    build_directory: str
    configuration: str = ""
    analyzers: list[str] = ["cmake"]
    configure: bool = False
    generator: str | None = None


def create_app(database: Path | None = None) -> FastAPI:
    store = Store(database or Path(os.getenv("ARCHMIND_DB", "archmind.db")))
    app = FastAPI(title="ArchMind", version="0.3.0")
    web = Path(__file__).parent / "web"

    @app.get("/", include_in_schema=False)
    def explorer():
        return HTMLResponse(
            '<!doctype html><html lang="en"><head><meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>ArchMind</title><link rel="stylesheet" href="/assets/main.css">'
            '</head><body><div id="root"></div><script type="module" src="/assets/main.js">'
            "</script></body></html>",
            headers={
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:"
            },
        )

    @app.get("/assets/{filename}", include_in_schema=False)
    def assets(filename: str):
        if filename not in {"main.js", "main.css"} or not (web / filename).is_file():
            raise NotFound("Asset not found")
        return FileResponse(
            web / filename, media_type="text/javascript" if filename.endswith(".js") else "text/css"
        )

    @app.exception_handler(NotFound)
    async def missing(_request, exc: NotFound):
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        )

    @app.exception_handler(ValueError)
    async def invalid(_request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}},
        )

    @app.post("/api/v1/projects", status_code=201)
    def add_project(body: ProjectInput):
        return store.project_add(body.name, Path(body.root_path))

    @app.get("/api/v1/projects")
    def projects():
        return {"items": store.projects()}

    @app.post("/api/v1/projects/{project_id}/analyses", status_code=202)
    def analyze(project_id: str, body: AnalysisInput, background: BackgroundTasks):
        if body.analyzers not in (["cmake"], ["cmake", "clang-uml"]):
            raise ValueError("Supported analyzers are ['cmake'] or ['cmake', 'clang-uml']")
        root = Path(store.project(project_id)["root_path"])
        build = Path(body.build_directory).resolve()
        if build != root and root not in build.parents:
            raise ValueError("Build directory must be inside the project root")
        if not body.configure and not build.is_dir():
            raise ValueError("Configured build directory does not exist")
        job_id = store.queue(project_id)

        def run():
            try:
                store.analyze(
                    project_id,
                    build,
                    body.configuration,
                    body.configure,
                    job_id,
                    analyzers=tuple(body.analyzers),
                    generator=body.generator,
                )
            except Exception as exc:
                logger.exception("ArchMind analysis job failed")
                with store.connect() as db:
                    db.execute(
                        "UPDATE jobs SET status='failed',diagnostics_json=? WHERE id=?",
                        (json.dumps([str(exc)]), job_id),
                    )

        background.add_task(run)
        return {
            "analysis_id": job_id,
            "status": "queued",
            "status_url": f"/api/v1/analyses/{job_id}",
        }

    @app.get("/api/v1/analyses/{analysis_id}")
    def analysis(analysis_id: str):
        return store.job(analysis_id)

    @app.get("/api/v1/projects/{project_id}/snapshots")
    def snapshots(project_id: str):
        return {"items": store.snapshots(project_id)}

    @app.get("/api/v1/snapshots/{snapshot_id}/nodes")
    def nodes(
        snapshot_id: str,
        kind: str | None = None,
        name: str | None = None,
        cursor: str | None = None,
        limit: int = Query(100, ge=1, le=500),
    ):
        return store.nodes(snapshot_id, kind, name, cursor, limit)

    @app.get("/api/v1/snapshots/{snapshot_id}/nodes/{node_id}")
    def node_detail(snapshot_id: str, node_id: str):
        return store.node_detail(snapshot_id, node_id)

    @app.get("/api/v1/snapshots/{snapshot_id}/edges")
    def edges(
        snapshot_id: str,
        source_id: str | None = None,
        target_id: str | None = None,
        kind: str | None = None,
        cursor: str | None = None,
        limit: int = Query(100, ge=1, le=500),
    ):
        return store.edges(snapshot_id, source_id, target_id, kind, cursor, limit)

    @app.get("/api/v1/snapshots/{snapshot_id}/cycles")
    def cycles(snapshot_id: str, kind: str = "BUILD_DEPENDS_ON"):
        if kind not in {"BUILD_DEPENDS_ON", "LINKS_TO", "INHERITS", "USES_TYPE", "DEPENDS_ON"}:
            raise ValueError("Unsupported cycle relationship kind")
        return {"items": store.cycles(snapshot_id, kind)}

    @app.get("/api/v1/snapshots/{snapshot_id}/subgraph")
    def subgraph(
        snapshot_id: str,
        center_id: str | None = None,
        depth: int = Query(1, ge=0, le=2),
        limit: int = Query(100, ge=1, le=200),
        cursor: str | None = None,
        kind: str | None = None,
        scope: str = "target",
    ):
        return store.subgraph(snapshot_id, center_id, depth, limit, cursor, kind, scope)

    @app.get("/api/v1/snapshots/{snapshot_id}/targets/{target_id}/symbols")
    def target_symbols(
        snapshot_id: str,
        target_id: str,
        limit: int = Query(100, ge=1, le=200),
        cursor: str | None = None,
    ):
        return store.target_symbols(snapshot_id, target_id, limit, cursor)

    @app.get("/api/v1/snapshots/{snapshot_id}/edges/{edge_id}/symbol-trace")
    def symbol_trace(snapshot_id: str, edge_id: str, limit: int = Query(100, ge=1, le=100)):
        return store.symbol_trace(snapshot_id, edge_id, limit)

    @app.get("/api/v1/snapshots/{snapshot_id}/impact")
    def impact(
        snapshot_id: str,
        symbol_id: str,
        depth: int = Query(2, ge=1, le=3),
        limit: int = Query(100, ge=1, le=200),
    ):
        return store.impact(snapshot_id, symbol_id, depth, limit)

    @app.get("/api/v1/snapshots/{snapshot_id}/edges/{edge_id}/evidence")
    def evidence(snapshot_id: str, edge_id: str):
        return store.evidence(snapshot_id, edge_id)

    @app.get("/api/v1/snapshots/{snapshot_id}/source")
    def source(
        snapshot_id: str,
        path: str,
        line: int = Query(1, ge=1),
        context: int = Query(5, ge=0, le=20),
    ):
        try:
            return store.source_excerpt(snapshot_id, path, line, context)
        except OSError as exc:
            raise NotFound("Source file not found") from exc

    return app
