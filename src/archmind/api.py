"""Loopback-first versioned REST API."""

import json
import logging
import os
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Query
from fastapi.responses import JSONResponse
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


def create_app(database: Path | None = None) -> FastAPI:
    store = Store(database or Path(os.getenv("ARCHMIND_DB", "archmind.db")))
    app = FastAPI(title="ArchMind", version="0.1.0")

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
        if body.analyzers != ["cmake"]:
            raise ValueError("M1 supports only the cmake analyzer")
        root = Path(store.project(project_id)["root_path"])
        build = Path(body.build_directory).resolve()
        if build != root and root not in build.parents:
            raise ValueError("Build directory must be inside the project root")
        if not body.configure and not build.is_dir():
            raise ValueError("Configured build directory does not exist")
        job_id = store.queue(project_id)

        def run():
            try:
                store.analyze(project_id, build, body.configuration, body.configure, job_id)
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
        if kind not in {"BUILD_DEPENDS_ON", "LINKS_TO"}:
            raise ValueError("Cycles require BUILD_DEPENDS_ON or LINKS_TO")
        return {"items": store.cycles(snapshot_id, kind)}

    @app.get("/api/v1/snapshots/{snapshot_id}/edges/{edge_id}/evidence")
    def evidence(snapshot_id: str, edge_id: str):
        return store.evidence(snapshot_id, edge_id)

    return app
