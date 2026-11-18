# ArchMind

**Architecture intelligence for complex codebases.**

Status: M1/M2 are implemented, an M3 semantic-analysis slice is available, and M4 provides read-only MCP plus opt-in selected-edge AI investigations. Python and frontend CI run on Linux and Windows; real clang-uml integration runs on Linux. Free-function/call analysis, incremental reindexing and guided refactoring remain planned.

## Requirements

Python 3.12+, CMake 3.20+, a C++ compiler, Git, Node.js 20+ with npm, and `uv` (or standards-compliant pip). For optional M3 indexing, install FOSS `clang-uml` 0.6.x and use a Ninja or Makefiles build that exports `compile_commands.json`. Windows also needs Ninja for the test fixture. All required software is free/open-source.

## Install and test

```sh
uv sync --extra dev
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
cd frontend
npm ci
npm run typecheck
npm test
npm run build
cd ..
```

On Windows use the equivalent commands in PowerShell; `scripts/bootstrap.ps1` runs install, tests and frontend build. `scripts/bootstrap.sh` does the same on Linux. With pip: `python -m pip install -e '.[dev]'`. The built frontend assets are included in the Python wheel and source distribution.

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

`uv run archmind serve` binds to `127.0.0.1:8000`. Open the explorer at `/`; OpenAPI docs are at `/docs`. API endpoints live under `/api/v1`. Register with `POST /api/v1/projects` (`name`, `root_path`), then queue with `POST /api/v1/projects/{id}/analyses` (`build_directory`, `configuration`, `analyzers: ["cmake"]`). Poll `/api/v1/analyses/{id}` for status and snapshot ID. Nodes and edges are paginated (`limit`, `cursor`); `/subgraph` returns capped target overviews/neighborhoods, `/cycles` returns SCCs, and edge evidence and guarded source excerpts are queryable. Project and build paths are validated locally. No source upload or AI service is required.

## Explorer (M2)

Select a project and completed snapshot, pan/zoom the graph, search targets across the snapshot, filter build-order and verified-link edges, expand a target neighborhood, or load the next overview page. Select an edge in the graph or relationship list to inspect evidence and open a source excerpt. Cycle members and edges are highlighted where the indexed relationship graph supports them. The view is capped at 200 target nodes and 500 edges per request; it does not attempt to render a whole large repository at once. See [M2 design and limits](docs/m2-explorer.md).

On Linux with Chromium installed, `cd frontend && npm run test:e2e` runs the Playwright browser smoke test against a disposable fixture server. The browser test is separate from the Python and frontend unit suites.

## C++ semantic indexing (M3 slice)

Use `uv run archmind analyze --project <project-id> --build-dir <project-root>/build-analysis --configure --generator Ninja --semantic` for a Ninja analysis build. `--semantic` runs clang-uml after CMake indexing and stores a new immutable snapshot. Set `ARCHMIND_CLANG_UML` to an executable path if clang-uml is not on `PATH`; `ARCHMIND_SEMANTIC_THREADS` bounds analyzer concurrency (1–32, default 1). The command requires `compile_commands.json`; Visual Studio generators do not generally provide it. The UI graph-level selector opens target, namespace and class views. Target selection lists source-owned classes; target-edge selection can show cross-target C++ relationships with evidence. The CLI also exposes `symbols`, `trace` and `impact` commands. See [M3 semantics and limitations](docs/m3-semantic.md).

## MCP and AI investigations (M4)

`uv run archmind mcp` starts the local stdio MCP server for external agents. The explorer can also ask questions about a selected target edge and review proposed dependency-removal alternatives. Configure `ARCHMIND_MODEL_BASE_URL` and `ARCHMIND_MODEL_NAME` for a local OpenAI-compatible model; without them, questions return a clear configuration error. The selected edge and snapshot are validated and retained across follow-ups. Model output is labeled as interpretation/proposal and cannot edit code. See [M4 usage and limitations](docs/m4-investigations.md).

## Provenance and limits

CMake codemodel dependencies mean build-order dependencies, not necessarily direct linker relationships. `LINKS_TO` requires a corroborating linker fragment and local backtrace; this may omit static-library links and external/imported libraries. Unknowns remain diagnostics, not invented nodes or links. File API lines are used only when provided. Analysis snapshots are immutable; failed analyses do not replace successful ones. See [ADR 0001](docs/decisions/0001-m1-boundaries.md).

The [OpenSceneGraph real-world check](docs/real-world-openscenegraph.md) documents a pinned upstream checkout, observed graph sizes, verified macro/link evidence and the limits of that validation.

ArchMind is licensed under [Apache-2.0](LICENSE), approved by the owner. The [dependency inventory](docs/LICENSES.md) lists required FOSS tools and release-audit work. See the [implementation specification](IMPLEMENTATION_SPEC.md) for the full roadmap and acceptance criteria.
