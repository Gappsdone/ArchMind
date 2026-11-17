"""Serve a configured disposable fixture for Playwright smoke tests."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import uvicorn

from archmind.api import create_app
from archmind.cmake import extract
from archmind.core import Store
from archmind.semantic import merge, normalize

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary) / "fixture"
    shutil.copytree(Path(__file__).resolve().parents[1] / "tests/fixtures/simple", root)
    build = root / "build"
    (build / ".cmake/api/v1/query").mkdir(parents=True)
    (build / ".cmake/api/v1/query/codemodel-v2").touch()
    subprocess.run(["cmake", "-S", str(root), "-B", str(build)], check=True, capture_output=True)
    store = Store(Path(temporary) / "archmind.db")
    project = store.project_add("Demo fixture", root)
    store.analyze(project["id"], build, "")
    semantic_root = Path(temporary) / "semantic"
    shutil.copytree(
        Path(__file__).resolve().parents[1] / "tests/fixtures/semantic",
        semantic_root,
        ignore=shutil.ignore_patterns(".scratch-*"),
    )
    semantic_build = semantic_root / "build"
    observation, metadata = extract(
        semantic_root, semantic_build, "", configure=True, export_compile_commands=True
    )
    document = json.loads((semantic_root / "architecture.json").read_text())
    semantic = normalize(semantic_root, document)
    semantic_project = store.project_add("Semantic fixture", semantic_root)
    snapshot_id = "playwright-semantic-snapshot"
    with store.connect() as db:
        db.execute(
            "INSERT INTO snapshots (id,project_id,cmake_config,build_directory,status,created_at) "
            "VALUES (?,?,?,?,'building',?)",
            (snapshot_id, semantic_project["id"], "", str(semantic_build), "now"),
        )
    store._publish(snapshot_id, merge(observation, semantic), metadata)
    uvicorn.run(create_app(store.path), host="127.0.0.1", port=8765, log_level="warning")
