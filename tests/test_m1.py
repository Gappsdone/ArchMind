import os
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archmind.api import create_app
from archmind.cmake import _artifact_for_fragment, _local_link_backtrace
from archmind.core import Store
from archmind.models import Edge, Node, Observation

FIXTURE = Path(__file__).parent / "fixtures/simple"


@pytest.fixture
def indexed(tmp_path):
    root = tmp_path / "fixture"
    shutil.copytree(FIXTURE, root)
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
    snapshot = db.analyze(project["id"], build, "")
    return db, project, snapshot, root, build


def targets(db, sid):
    return {n["name"]: n for n in db.nodes(sid, kind="CMAKE_TARGET")["items"]}


def links(db, sid, name, kind="BUILD_DEPENDS_ON"):
    nodes = targets(db, sid)
    edges = db.edges(sid, source_id=nodes[name]["id"], kind=kind)["items"]
    return {n for n, item in nodes.items() if item["id"] in {e["target_id"] for e in edges}}


def test_index_links_sources_evidence_and_reverse(indexed):
    db, _, snapshot, _, _ = indexed
    sid = snapshot["id"]
    assert set(targets(db, sid)) == {"Application", "Simulation", "Physics", "Math"}
    assert links(db, sid, "Simulation") == {"Physics", "Math"}
    assert links(db, sid, "Application") == {"Simulation", "Physics", "Math"}
    if os.name != "nt":
        assert links(db, sid, "Application", "LINKS_TO") == {"Simulation"}
    assert links(db, sid, "Simulation", "LINKS_TO") == set()
    nodes = targets(db, sid)
    assert len(db.edges(sid, target_id=nodes["Math"]["id"], kind="BUILD_DEPENDS_ON")["items"]) >= 2
    assert len(db.edges(sid, source_id=nodes["Math"]["id"], kind="OWNS_FILE")["items"]) == 1
    if os.name != "nt":
        edge = db.edges(sid, source_id=nodes["Application"]["id"], kind="LINKS_TO")["items"][0]
        ev = db.evidence(sid, edge["id"])["evidence"][0]
        assert ev["file_path"] == "app/CMakeLists.txt"
        assert ev["line_start"] == 2
    assert db.cycles(sid) == []


def test_snapshot_immutability_and_failure(indexed):
    db, project, old, root, build = indexed
    assert links(db, old["id"], "Simulation") == {"Physics", "Math"}
    (root / "simulation/CMakeLists.txt").write_text(
        "add_library(Simulation STATIC simulation.cpp)\n"
    )
    new = db.analyze(project["id"], build, "", configure=True)
    assert links(db, new["id"], "Simulation") == set()
    assert links(db, old["id"], "Simulation") == {"Physics", "Math"}
    with pytest.raises(ValueError):
        db.analyze(project["id"], root / "missing", "")
    assert db.snapshots(project["id"])[0]["status"] == "complete"


def test_api_and_pagination(indexed):
    db, project, snap, _, _ = indexed
    client = TestClient(create_app(db.path))
    assert client.get("/api/v1/snapshots/missing/nodes").status_code == 404
    first = client.get(f"/api/v1/snapshots/{snap['id']}/nodes?limit=2").json()
    second = client.get(
        f"/api/v1/snapshots/{snap['id']}/nodes", params={"limit": 2, "cursor": first["next_cursor"]}
    ).json()
    assert first["next_cursor"] and second["items"]
    assert {n["id"] for n in first["items"]}.isdisjoint({n["id"] for n in second["items"]})
    assert client.get(f"/api/v1/projects/{project['id']}/snapshots").status_code == 200
    assert client.get(f"/api/v1/snapshots/{snap['id']}/cycles").json() == {"items": []}


def test_failed_file_api_preserves_last_snapshot(indexed):
    db, project, old, _, build = indexed
    for index in (build / ".cmake/api/v1/reply").glob("index-*.json"):
        index.write_text("broken")
    with pytest.raises(ValueError):
        db.analyze(project["id"], build, "")
    statuses = [s["status"] for s in db.snapshots(project["id"])]
    assert set(statuses) == {"complete", "failed"}
    assert links(db, old["id"], "Simulation") == {"Physics", "Math"}


def test_real_cmake_static_link_cycle_not_fabricated(tmp_path):
    root = tmp_path / "cycle"
    shutil.copytree(Path(__file__).parent / "fixtures/cycle", root)
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
    db = Store(tmp_path / "cycle.db")
    project = db.project_add("Cycle", root)
    sid = db.analyze(project["id"], build, "")["id"]
    assert set(targets(db, sid)) == {"A", "B"}
    # CMake File API does not expose static-library link clauses as link
    # fragments and can collapse their build-order cycle. Do not invent it.
    assert db.cycles(sid) == []


def test_scc_detects_cycles_and_self_loops(tmp_path):
    db = Store(tmp_path / "graph.db")
    project = db.project_add("Cycle", Path(__file__).parent / "fixtures/cycle")
    sid = "synthetic"
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO snapshots (id,project_id,cmake_config,build_directory,status,created_at) VALUES (?,?,?,?,'building',?)",
            (sid, project["id"], "", "", "now"),
        )
    db._publish(
        sid,
        Observation(
            (
                Node("A", "CMAKE_TARGET", "A"),
                Node("B", "CMAKE_TARGET", "B"),
                Node("C", "CMAKE_TARGET", "C"),
            ),
            (
                Edge("A", "B", "BUILD_DEPENDS_ON", "declared"),
                Edge("B", "A", "BUILD_DEPENDS_ON", "declared"),
                Edge("C", "C", "BUILD_DEPENDS_ON", "declared"),
            ),
        ),
        {},
    )
    assert sorted(map(len, db.cycles(sid))) == [1, 2]


def test_api_job_lifecycle(indexed):
    db, project, _, _, build = indexed
    client = TestClient(create_app(db.path))
    response = client.post(
        f"/api/v1/projects/{project['id']}/analyses",
        json={"build_directory": str(build), "configuration": "", "analyzers": ["cmake"]},
    )
    assert response.status_code == 202
    job = client.get(response.json()["status_url"]).json()
    assert job["status"] == "completed"
    assert job["snapshot_id"]
    assert client.get(f"/api/v1/snapshots/{job['snapshot_id']}/nodes").status_code == 200


def test_external_link_is_diagnostic_not_fabricated(tmp_path):
    root = tmp_path / "external"
    shutil.copytree(Path(__file__).parent / "fixtures/external", root)
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
    db = Store(tmp_path / "external.db")
    project = db.project_add("External", root)
    result = db.analyze(project["id"], build, "")
    assert any("Unresolved linker fragment" in item for item in result["diagnostics"])
    assert db.nodes(result["id"], kind="EXTERNAL_LIBRARY")["items"] == []


def test_versioned_shared_library_fragment_and_macro_backtrace():
    artifacts = {"lib/libosg.so": "osg-id", "lib/libosgDB.so": "osgdb-id"}
    assert _artifact_for_fragment("lib/libosg.so.3.7.0", artifacts) == "osg-id"
    assert _artifact_for_fragment("lib/libosgDB.so.3", artifacts) == "osgdb-id"
    assert _artifact_for_fragment("lib/libosg.so.fake", artifacts) is None
    assert _artifact_for_fragment("lib/libosgDB.so.3", {"lib/libosg.so": "osg-id"}) is None

    target = {
        "backtraceGraph": {
            "files": [
                "src/osgViewer/CMakeLists.txt",
                "CMakeModules/OsgMacroUtils.cmake",
                "src/osg/CMakeLists.txt",
            ],
            "commands": ["SETUP_LIBRARY", "LINK_INTERNAL", "TARGET_LINK_LIBRARIES"],
            "nodes": [
                {"file": 0},
                {"file": 0, "line": 280, "command": 0, "parent": 0},
                {"file": 1, "line": 245, "command": 1, "parent": 1},
                {"file": 1, "line": 54, "command": 2, "parent": 2},
                {"file": 2},
                {"file": 2, "line": 465, "command": 0, "parent": 4},
                {"file": 1, "line": 54, "command": 2, "parent": 5},
            ],
        }
    }
    evidence = _local_link_backtrace(target, 3, "src/osgViewer")
    assert evidence is not None
    assert evidence[:2] == ("CMakeModules/OsgMacroUtils.cmake", 54)
    assert "src/osgViewer/CMakeLists.txt:280" in evidence[2]
    assert _local_link_backtrace(target, 6, "src/osgViewer") is None


@pytest.mark.skipif(os.name == "nt", reason="ELF versioned .so names are Linux-specific")
def test_real_cmake_versioned_shared_library_link_through_macro(tmp_path):
    root = tmp_path / "versioned"
    (root / "cmake").mkdir(parents=True)
    (root / "app").mkdir()
    (root / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.20)\n"
        "project(Versioned LANGUAGES CXX)\n"
        "include(cmake/Link.cmake)\n"
        "add_library(Core SHARED core.cpp)\n"
        "set_target_properties(Core PROPERTIES VERSION 2.1 SOVERSION 2)\n"
        "add_subdirectory(app)\n"
    )
    (root / "cmake/Link.cmake").write_text(
        "macro(link_internal target)\n"
        "  target_link_libraries(${target} PRIVATE ${ARGN})\n"
        "endmacro()\n"
    )
    (root / "core.cpp").write_text("int core() { return 42; }\n")
    (root / "app/CMakeLists.txt").write_text(
        "add_executable(App main.cpp)\nlink_internal(App Core)\n"
    )
    (root / "app/main.cpp").write_text("int core(); int main() { return core() == 42 ? 0 : 1; }\n")
    build = root / "build"
    (build / ".cmake/api/v1/query").mkdir(parents=True)
    (build / ".cmake/api/v1/query/codemodel-v2").touch()
    subprocess.run(
        ["cmake", "-S", str(root), "-B", str(build), "-G", "Unix Makefiles"],
        check=True,
        capture_output=True,
    )
    db = Store(tmp_path / "versioned.db")
    project = db.project_add("Versioned", root)
    sid = db.analyze(project["id"], build, "")["id"]
    assert links(db, sid, "App", "LINKS_TO") == {"Core"}
    app = targets(db, sid)["App"]
    edge = db.edges(sid, source_id=app["id"], kind="LINKS_TO")["items"][0]
    evidence = db.evidence(sid, edge["id"])["evidence"][0]
    assert evidence["file_path"] == "cmake/Link.cmake"
    assert evidence["line_start"] == 2
    assert "app/CMakeLists.txt:2" in evidence["description"]


def test_failed_api_job_diagnostics(indexed):
    db, project, _, _, build = indexed
    for index in (build / ".cmake/api/v1/reply").glob("index-*.json"):
        index.write_text("broken")
    client = TestClient(create_app(db.path))
    response = client.post(
        f"/api/v1/projects/{project['id']}/analyses",
        json={"build_directory": str(build), "configuration": "", "analyzers": ["cmake"]},
    )
    assert response.status_code == 202
    job = client.get(response.json()["status_url"]).json()
    assert job["status"] == "failed"
    assert job["diagnostics"]
