"""Bounded graph and source-preview API contracts for the M2 explorer."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_m1 import targets

from archmind.api import create_app
from archmind.core import Store


@pytest.fixture
def graph(tmp_path):
    root = tmp_path / "fixture"
    shutil.copytree(Path(__file__).parent / "fixtures/simple", root)
    build = root / "build"
    (build / ".cmake/api/v1/query").mkdir(parents=True)
    (build / ".cmake/api/v1/query/codemodel-v2").touch()
    subprocess.run(
        [
            "cmake",
            "-S",
            str(root),
            "-B",
            str(build),
            *(["-G", "Ninja"] if os.name == "nt" else ["-G", "Unix Makefiles"]),
        ],
        check=True,
        capture_output=True,
    )
    db = Store(tmp_path / "archmind.db")
    project = db.project_add("Fixture", root)
    return db, db.analyze(project["id"], build, ""), root


def test_overview_is_bounded_and_pageable(graph):
    db, snapshot, _ = graph
    sid = snapshot["id"]
    first = db.subgraph(sid, limit=2)
    second = db.subgraph(sid, limit=2, cursor=first["next_cursor"])
    assert first["truncated"]
    assert len(first["nodes"]) == len(second["nodes"]) == 2
    assert {n["id"] for n in first["nodes"]}.isdisjoint({n["id"] for n in second["nodes"]})
    for page in (first, second):
        ids = {node["id"] for node in page["nodes"]}
        assert all(edge["source_id"] in ids and edge["target_id"] in ids for edge in page["edges"])


def test_neighborhood_and_kind_filter(graph):
    db, snapshot, _ = graph
    sid = snapshot["id"]
    center = targets(db, sid)["Simulation"]["id"]
    result = db.subgraph(sid, center_id=center, depth=1, limit=4)
    assert {n["name"] for n in result["nodes"]} == {"Application", "Simulation", "Physics", "Math"}
    kinds = {edge["kind"] for edge in result["edges"]}
    assert "BUILD_DEPENDS_ON" in kinds
    assert kinds <= {"BUILD_DEPENDS_ON", "LINKS_TO"}
    # Windows/Ninja codemodels need not expose a corroborated linker fragment.
    if os.name != "nt":
        assert "LINKS_TO" in kinds
    links = db.subgraph(sid, center_id=center, kind="LINKS_TO")
    assert all(e["kind"] == "LINKS_TO" for e in links["edges"])
    with pytest.raises(ValueError):
        db.subgraph(sid, limit=201)
    with pytest.raises(ValueError):
        db.subgraph(sid, depth=3)


def test_explorer_assets_and_api_contract(graph):
    db, snapshot, _ = graph
    client = TestClient(create_app(db.path))
    shell = client.get("/")
    assert shell.status_code == 200
    assert "ArchMind" in shell.text
    assert client.get("/assets/main.js").status_code == 200
    assert client.get("/assets/main.css").status_code == 200
    assert client.get("/assets/unknown.js").status_code == 404
    subgraph = client.get(f"/api/v1/snapshots/{snapshot['id']}/subgraph", params={"limit": 2})
    assert subgraph.status_code == 200
    assert len(subgraph.json()["nodes"]) == 2
    assert (
        client.get(f"/api/v1/snapshots/{snapshot['id']}/subgraph", params={"depth": 3}).status_code
        == 422
    )


def test_source_preview_and_traversal_guard(graph, tmp_path):
    db, snapshot, root = graph
    sid = snapshot["id"]
    client = TestClient(create_app(db.path))
    response = client.get(
        f"/api/v1/snapshots/{sid}/source", params={"path": "simulation/CMakeLists.txt", "line": 2}
    )
    assert response.status_code == 200
    assert response.json()["lines"][1]["number"] == 2
    assert "target_link_libraries" in response.json()["lines"][1]["text"]
    assert (
        client.get(f"/api/v1/snapshots/{sid}/source", params={"path": "../secret"}).status_code
        == 400
    )
    outside = tmp_path / "outside.cpp"
    outside.write_text("private")
    try:
        (root / "linked.cpp").symlink_to(outside)
    except (OSError, NotImplementedError):
        # Some Windows runners cannot create symlinks. Traversal is already
        # checked above; the symlink guard is tested where supported.
        pass
    else:
        assert (
            client.get(f"/api/v1/snapshots/{sid}/source", params={"path": "linked.cpp"}).status_code
            == 400
        )
    assert client.get("/api/v1/snapshots/missing/subgraph").status_code == 404
