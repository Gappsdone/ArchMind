#!/usr/bin/env sh
set -eu
uv sync --extra dev
uv run pytest -q
