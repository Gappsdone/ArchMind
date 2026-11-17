# ArchMind

**Architecture intelligence for complex codebases.**

Status: Milestone 1 implementation in progress. CMake target indexing, immutable SQLite snapshots, CLI, REST queries, and cycle detection are available on Linux; Windows CI is configured but not yet verified. React exploration, C++ symbol analysis, MCP/AI and guided refactoring are planned, not implemented.

## Requirements

Python 3.12+, CMake 3.20+, a C++ compiler, Git, and `uv` (or standards-compliant pip). Windows also needs Ninja for the test fixture. All required software is free/open-source.

## Install and test

```sh
uv sync --extra dev
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
```

On Windows use the equivalent commands in PowerShell; `scripts/bootstrap.ps1` runs install and tests. `scripts/bootstrap.sh` does the same on Linux. With pip: `python -m pip install -e '.[dev]'`.

## Analyze the sample project

Configure the sample project with a File API query (commands below are for a POSIX shell):

```sh
mkdir -p tests/fixtures/simple/build/.cmake/api/v1/query
: > tests/fixtures/simple/build/.cmake/api/v1/query/codemodel-v2
cmake -S tests/fixtures/simple -B tests/fixtures/simple/build
export ARCHMIND_DB="$PWD/archmind.db"
uv run archmind project add --name Demo --root tests/fixtures/simple
uv run archmind analyze --project <project-id> --build-dir tests/fixtures/simple/build
uv run archmind targets --snapshot <snapshot-id>
uv run archmind dependencies --snapshot <snapshot-id> --target 'CMAKE_TARGET:Simulation:simulation'
uv run archmind cycles --snapshot <snapshot-id>
uv run archmind evidence --snapshot <snapshot-id> --edge <edge-id>
```

Use the IDs returned by the preceding commands. `--configure` on `analyze` can create/update the File API reply in a build directory inside the project. `dependencies --reverse` shows incoming edges. Default relationship is `BUILD_DEPENDS_ON`; select `--kind LINKS_TO` for verified link edges. IDs are snapshot-local; stable keys persist across equivalent snapshots.

## REST

`uv run archmind serve` binds to `127.0.0.1:8000`; OpenAPI docs are at `/docs`. API endpoints live under `/api/v1`. Register with `POST /api/v1/projects` (`name`, `root_path`), then queue with `POST /api/v1/projects/{id}/analyses` (`build_directory`, `configuration`, `analyzers: ["cmake"]`). Poll `/api/v1/analyses/{id}` for status and snapshot ID. Nodes and edges are paginated (`limit`, `cursor`); cycles and edge evidence are queryable. Project and build paths are validated locally. No source upload or AI service is required.

## Provenance and limits

CMake codemodel dependencies mean build-order dependencies, not necessarily direct linker relationships. `LINKS_TO` requires a corroborating linker fragment and local backtrace; this may omit static-library links and external/imported libraries. Unknowns remain diagnostics, not invented nodes or links. File API lines are used only when provided. Analysis snapshots are immutable; failed analyses do not replace successful ones. See [ADR 0001](docs/decisions/0001-m1-boundaries.md).

ArchMind has **no project license yet**; Apache-2.0 is proposed pending owner approval. The [dependency inventory](docs/LICENSES.md) lists required FOSS tools and release-audit work. See the [implementation specification](IMPLEMENTATION_SPEC.md) for the full roadmap and acceptance criteria.
