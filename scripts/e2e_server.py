"""Serve a configured disposable fixture for Playwright smoke tests."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import uvicorn

from archmind.api import create_app
from archmind.core import Store

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
    uvicorn.run(create_app(store.path), host="127.0.0.1", port=8765, log_level="warning")
