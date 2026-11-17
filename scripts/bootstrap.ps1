$ErrorActionPreference = "Stop"
uv sync --extra dev
uv run pytest -q
Push-Location frontend
try {
  npm ci
  npm run typecheck
  npm test
  npm run build
} finally {
  Pop-Location
}
