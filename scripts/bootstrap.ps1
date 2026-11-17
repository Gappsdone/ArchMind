$ErrorActionPreference = "Stop"
uv sync --extra dev
uv run pytest -q
