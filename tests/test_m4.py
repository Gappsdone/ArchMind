"""M4 selected-edge context, MCP and evidence-bound proposal contracts."""

import asyncio
import json

import httpx
import pytest
import test_m1
from fastapi.testclient import TestClient

from archmind.api import create_app
from archmind.investigations import LocalModel
from archmind.mcp_server import create_mcp_server
from archmind.query_service import ArchitectureQueries

targets = test_m1.targets
graph = test_m1.indexed


def _selection(db, project, snapshot):
    sid = snapshot["id"]
    nodes = targets(db, sid)
    edge = db.edges(sid, source_id=nodes["Application"]["id"], kind="BUILD_DEPENDS_ON")["items"][0]
    return {
        "project_id": project["id"],
        "snapshot_id": sid,
        "edge_id": edge["id"],
        "source_id": edge["source_id"],
        "target_id": edge["target_id"],
        "relationship": edge["kind"],
    }


def test_mcp_tools_share_bounded_query_service(graph):
    db, project, snapshot, *_ = graph
    sid = snapshot["id"]
    selection = _selection(db, project, snapshot)
    queries = ArchitectureQueries(db)
    assert (
        queries.explain_dependency_context(sid, selection["edge_id"])["relationship"]
        == "BUILD_DEPENDS_ON"
    )
    assert queries.find_dependency_paths(
        sid, selection["source_id"], selection["target_id"], kind="BUILD_DEPENDS_ON"
    )["items"]
    with pytest.raises(ValueError):
        queries.find_dependency_paths(
            sid, selection["source_id"], selection["target_id"], max_depth=99
        )

    async def run():
        server = create_mcp_server(db.path)
        assert {tool.name for tool in await server.list_tools()} == {
            "list_projects",
            "list_targets",
            "get_dependencies",
            "get_dependency_evidence",
            "find_dependency_paths",
            "detect_cycles",
            "explain_dependency_context",
            "get_refactoring_context",
        }
        result = await server.call_tool(
            "explain_dependency_context", {"snapshot_id": sid, "edge_id": selection["edge_id"]}
        )
        assert not result.is_error
        payload = result.structured_content or json.loads(result.content[0].text)
        assert payload["relationship"] == "BUILD_DEPENDS_ON"
        assert payload["project_id"] == project["id"]

    asyncio.run(run())


def test_investigation_context_immutability_and_no_model(graph):
    db, project, snapshot, *_ = graph
    client = TestClient(create_app(db.path, LocalModel(base_url="", model="")))
    selection = _selection(db, project, snapshot)
    forged = {**selection, "target_id": selection["source_id"]}
    assert client.post("/api/v1/investigations", json=forged).status_code == 400
    created = client.post("/api/v1/investigations", json=selection)
    assert created.status_code == 201
    iid = created.json()["id"]
    assert created.json()["context"]["edge_id"] == selection["edge_id"]
    assert (
        client.post(f"/api/v1/investigations/{iid}/messages", json={"question": "Why?"}).status_code
        == 409
    )
    persisted = client.get(f"/api/v1/investigations/{iid}").json()
    assert persisted["turns"] == []
    assert {key: persisted[key] for key in selection} == selection
    assert client.get("/api/v1/investigations/missing").status_code == 404


def test_local_model_reply_validation_and_followups(graph):
    db, project, snapshot, *_ = graph
    selection = _selection(db, project, snapshot)
    evidence = db.evidence(snapshot["id"], selection["edge_id"])["evidence"]
    citation = evidence[0]["id"] if evidence else "unknown"
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        response = {
            "answer": "A plan worth reviewing, not an applied change.",
            "findings": [
                {"text": "Grounded relationship", "citation_ids": [citation]},
                {"text": "Invented fact", "citation_ids": ["fake-id"]},
            ],
            "hypotheses": ["Header ownership may be incomplete"],
            "uncertainty": [],
            "alternatives": [
                {
                    "title": "Extract adapter",
                    "rationale": "Isolate dependency",
                    "impact": "Build and tests needed",
                    "tradeoffs": ["More target boundaries"],
                    "risks": ["Link order"],
                    "affected_targets": ["InventedTarget", "Application"],
                    "affected_files": ["../secret.cpp"],
                    "complexity": "medium",
                    "plan_steps": ["Propose edit", "Build and test"],
                }
            ],
        }
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(response)}}]}
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    model = LocalModel("http://127.0.0.1:1234/v1", "local-test", client)
    api = TestClient(create_app(db.path, model))
    iid = api.post("/api/v1/investigations", json=selection).json()["id"]
    first = api.post(
        f"/api/v1/investigations/{iid}/messages", json={"question": "Explain this"}
    ).json()
    assert first["status"] == "proposal_only"
    assert first["selected_edge"] == selection
    assert "Invented fact" in first["hypotheses"]
    assert first["alternatives"][0]["affected_targets"] == ["Application"]
    assert first["alternatives"][0]["affected_files"] == []
    assert "build-order" in " ".join(first["uncertainty"])
    second = api.post(
        f"/api/v1/investigations/{iid}/messages", json={"question": "How to remove it?"}
    ).json()
    assert second["selected_edge"] == selection
    assert len(calls[1]["messages"]) > len(calls[0]["messages"])
    persisted = api.get(f"/api/v1/investigations/{iid}").json()
    assert len(persisted["turns"]) == 4
    assert persisted["turns"][0]["content"] == "Explain this"


def test_remote_model_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("ARCHMIND_ALLOW_REMOTE_MODEL", raising=False)
    with pytest.raises(ValueError, match="Remote model endpoint requires"):
        LocalModel("https://example.com/v1", "model")


def test_mcp_stdio_transport(graph):
    import os
    import sys

    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    db, project, snapshot, *_ = graph

    async def run():
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "archmind.cli", "mcp"],
            env={**os.environ, "ARCHMIND_DB": str(db.path)},
        )
        async with stdio_client(server) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert "explain_dependency_context" in {tool.name for tool in tools.tools}
                projects = await session.call_tool("list_projects", {})
                assert not projects.is_error
                assert project["id"] in str(projects)
                targets_result = await session.call_tool(
                    "list_targets", {"snapshot_id": snapshot["id"]}
                )
                assert not targets_result.is_error
                assert "Application" in str(targets_result)

    asyncio.run(run())


def test_existing_m1_database_upgrades_without_losing_projects(tmp_path):
    import sqlite3

    from archmind.core import SCHEMA, Store

    path = tmp_path / "old.db"
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        db.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        db.execute("INSERT INTO alembic_version VALUES ('0001_initial')")
        db.execute("INSERT INTO projects VALUES ('existing','Legacy Fixture','/fixture','now')")
    store = Store(path)
    assert store.projects()[0]["id"] == "existing"
    with store.connect() as db:
        assert (
            db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "0002_investigations"
        )
        assert db.execute("SELECT name FROM sqlite_master WHERE name='investigations'").fetchone()
