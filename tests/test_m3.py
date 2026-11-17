"""M3 semantic graph contracts using a real clang-uml schema-v3 fixture."""

import json
import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archmind.api import create_app
from archmind.core import Store
from archmind.semantic import normalize

FIXTURE = Path(__file__).parent / "fixtures/semantic"


@pytest.fixture
def semantic_graph(tmp_path, monkeypatch):
    root = tmp_path / "semantic"
    shutil.copytree(FIXTURE, root, ignore=shutil.ignore_patterns(".scratch-*"))
    document = json.loads((root / "architecture.json").read_text())
    observation = normalize(root, document)
    monkeypatch.setattr(
        "archmind.semantic.run", lambda _root, _build: (observation, {"clang_uml_version": "0.6.3"})
    )
    db = Store(tmp_path / "archmind.db")
    project = db.project_add("Semantic", root)
    snapshot = db.analyze(
        project["id"], root / "build", "", configure=True, analyzers=("cmake", "clang-uml")
    )
    return db, snapshot["id"], root


def _node(db, sid, kind, name):
    return next(
        node for node in db.nodes(sid, kind=kind, limit=200)["items"] if node["name"] == name
    )


def test_normalized_classes_methods_and_provenance(semantic_graph):
    db, sid, _ = semantic_graph
    assert {n["name"] for n in db.nodes(sid, kind="CLASS")["items"]} == {
        "Base",
        "Derived",
        "Runner",
    }
    assert {n["name"] for n in db.nodes(sid, kind="METHOD")["items"]} >= {"run", "calculate"}
    assert {n["name"] for n in db.nodes(sid, kind="NAMESPACE")["items"]} == {"app", "domain"}
    symbol_graph = db.subgraph(sid, scope="symbol")
    assert {e["kind"] for e in symbol_graph["edges"]} == {"INHERITS", "USES_TYPE"}
    namespace_graph = db.subgraph(sid, scope="namespace")
    assert {n["name"] for n in namespace_graph["nodes"]} == {"app", "domain"}
    dependency = next(e for e in namespace_graph["edges"] if e["kind"] == "DEPENDS_ON")
    assert dependency["origin"] == "derived"
    assert db.evidence(sid, dependency["id"])["evidence"][0]["line_start"] == 9
    inheritance = next(e for e in symbol_graph["edges"] if e["kind"] == "INHERITS")
    assert db.evidence(sid, inheritance["id"])["evidence"][0]["line_start"] is None
    use = next(e for e in symbol_graph["edges"] if e["kind"] == "USES_TYPE")
    evidence = db.evidence(sid, use["id"])["evidence"][0]
    assert (evidence["file_path"], evidence["line_start"]) == ("app/runner.hpp", 9)


def test_target_drilldown_trace_and_impact(semantic_graph):
    db, sid, _ = semantic_graph
    app = _node(db, sid, "CMAKE_TARGET", "AppCore")
    domain = _node(db, sid, "CMAKE_TARGET", "Domain")
    assert {x["name"] for x in db.target_symbols(sid, app["id"])["items"]} == {"Runner"}
    assert {x["name"] for x in db.target_symbols(sid, domain["id"])["items"]} == {"Base", "Derived"}
    first_page = db.target_symbols(sid, domain["id"], limit=1)
    second_page = db.target_symbols(sid, domain["id"], limit=1, cursor=first_page["next_cursor"])
    assert first_page["next_cursor"] and second_page["next_cursor"] is None
    assert first_page["items"][0]["id"] != second_page["items"][0]["id"]
    target_edge = next(
        e
        for e in db.edges(sid, source_id=app["id"], target_id=domain["id"])["items"]
        if e["kind"] == "BUILD_DEPENDS_ON"
    )
    trace = db.symbol_trace(sid, target_edge["id"])
    assert [(x["source_name"], x["target_name"], x["kind"]) for x in trace["items"]] == [
        ("Runner", "Base", "USES_TYPE")
    ]
    assert trace["items"][0]["evidence"][0]["line_start"] == 9
    base = _node(db, sid, "CLASS", "Base")
    assert db.node_detail(sid, base["id"])["metadata"]["file_path"] == "domain/base.hpp"
    impact = db.impact(sid, base["id"])
    assert {x["name"] for x in impact["items"]} == {"Runner", "Derived"}
    assert {x["name"] for x in impact["affected_targets"]} == {"AppCore", "Domain"}


def test_semantic_api_and_bounds(semantic_graph):
    db, sid, _ = semantic_graph
    client = TestClient(create_app(db.path))
    graph = client.get(f"/api/v1/snapshots/{sid}/subgraph", params={"scope": "symbol", "limit": 2})
    assert graph.status_code == 200
    assert len(graph.json()["nodes"]) == 2
    assert (
        client.get(f"/api/v1/snapshots/{sid}/subgraph", params={"scope": "unknown"}).status_code
        == 400
    )
    base = _node(db, sid, "CLASS", "Base")
    assert (
        client.get(f"/api/v1/snapshots/{sid}/impact", params={"symbol_id": base["id"]}).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/snapshots/{sid}/impact", params={"symbol_id": base["id"], "depth": 4}
        ).status_code
        == 422
    )


def test_clang_uml_schema_rejection_and_path_guard(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(ValueError):
        normalize(root, {"diagram_type": "class", "metadata": {"schema_version": 99}})
    document = json.loads((FIXTURE / "architecture.json").read_text())
    result = normalize(root, document)
    assert all(n.metadata.get("file_path") is None for n in result.nodes if n.kind == "CLASS")
    assert any("outside project or missing" in d for d in result.diagnostics)


def test_missing_compilation_database_fails_without_replacing_snapshot(tmp_path):
    root = tmp_path / "semantic"
    shutil.copytree(FIXTURE, root, ignore=shutil.ignore_patterns(".scratch-*"))
    db = Store(tmp_path / "state.db")
    project = db.project_add("Semantic", root)
    with pytest.raises(ValueError, match="Generator"):
        db.analyze(project["id"], root / "build", "", configure=True, generator="untrusted")
    old = db.analyze(project["id"], root / "build", "", configure=True)
    with pytest.raises(ValueError, match="compile_commands.json"):
        db.analyze(project["id"], root / "build", "", analyzers=("cmake", "clang-uml"))
    assert {s["status"] for s in db.snapshots(project["id"])} == {"complete", "failed"}
    assert db.nodes(old["id"], kind="CMAKE_TARGET")["items"]


@pytest.mark.skipif(not os.getenv("ARCHMIND_CLANG_UML"), reason="clang-uml executable not provided")
def test_real_clang_uml_invocation(tmp_path):
    root = tmp_path / "semantic"
    shutil.copytree(FIXTURE, root, ignore=shutil.ignore_patterns(".scratch-*"))
    db = Store(tmp_path / "real.db")
    project = db.project_add("Real clang-uml", root)
    snapshot = db.analyze(
        project["id"], root / "build", "", configure=True, analyzers=("cmake", "clang-uml")
    )
    assert {n["name"] for n in db.nodes(snapshot["id"], kind="CLASS")["items"]} == {
        "Base",
        "Derived",
        "Runner",
    }
