#!/usr/bin/env sh
set -eu
uv sync --extra dev
uv run pytest -q
(cd frontend && npm ci && npm run typecheck && npm test && npm run build)
