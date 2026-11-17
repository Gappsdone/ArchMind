# ArchMind — C++ Architecture Intelligence & AI-Assisted Refactoring Platform

**Status:** Implementation baseline, v1.0  
**Date:** 2026-11-17  
**Audience:** Autonomous or assisted software engineering agent  
**Initial target:** Windows and Linux, local-first, strictly free and open-source software (FOSS)

## 0. Agent instructions

Implement **ArchMind** incrementally, starting with Milestone 1 (M1). Treat this document as the product and engineering contract. Do not claim features are implemented until they are covered by executable tests. Prefer a small, functioning vertical slice over speculative scaffolding. Record unavoidable design deviations as architecture decision records (ADRs). Never invent source locations, dependencies, or test results.

**First deliverable:** a runnable Python package (`archmind`) and CLI (`archmind`) that extracts a CMake target dependency graph from the CMake File API, persists an immutable snapshot in SQLite, exposes dependency queries, and passes cross-platform fixture tests. The REST API is part of M1. The React UI, C++ symbol analysis, MCP integration and refactoring belong to subsequent milestones.

### Non-negotiable engineering rules

- Strict FOSS for all required dependencies, including development and CI tooling. Maintain an SPDX license inventory; propose Apache-2.0 for the project itself pending owner approval.
- Preserve the distinction between declared, semantic and derived dependencies. Never equate CMake build-order dependencies with linker relationships.
- Every reported relationship must carry source provenance or an explicit `unresolved`/`derived` status; unknown source lines are `null`.
- Store immutable completed snapshots; failed analyses must not replace the last successful snapshot.
- The backend and MCP server share one query service; neither the UI nor MCP directly accesses SQLite.
- No automatic AI edits or merges without user approval. All edits must occur in an isolated Git worktree and be validated by build/tests.
- Never execute user-supplied arbitrary commands through the API. Bind local HTTP service to `127.0.0.1` by default; validate and constrain repository paths.
- Support Windows and Linux from M1. Use pathlib, avoid shell-specific assumptions, and test with GitHub Actions or an equivalent FOSS-compatible runner.
- If a requirement cannot be implemented reliably with CMake File API metadata alone, represent the limitation explicitly rather than heuristically asserting facts.

## 1. Product goals and scope

Build **ArchMind**, a local-first developer platform for large (500k–2M LOC) C++/CMake projects to:

1. Discover and index build targets, source files, packages, namespaces, classes and methods.
2. Explore interactive dependencies between targets, packages, classes and functions.
3. Explain where a dependency originates, with navigable, verifiable source evidence.
4. Detect cycles, coupling, architectural violations and potential change impact.
5. Let an architect select a dependency edge and ask an AI agent questions about it.
6. Propose dependency-removal strategies, review them, apply approved refactorings and validate architectural outcomes.
7. Support local LLMs via external MCP-capable coding agents, including OpenCode.

### Official project identity

| Identity | Canonical value |
|---|---|
| Product name | **ArchMind** |
| Tagline | Architecture intelligence for complex codebases |
| Repository name | `archmind` |
| Python distribution | `archmind` |
| Python import package | `archmind` (`src/archmind/`) |
| CLI executable | `archmind` |
| API base path | `/api/v1` (unchanged) |
| Web UI title | `ArchMind` |
| Default SQLite filename | `archmind.db` |
| Python entry point | `[project.scripts] archmind = "archmind.cli:app"` (if using Typer) |

Do not use the legacy names `cpp-arch`, `cpp_arch`, or `cpp-architecture-analyzer` in generated source, packaging, commands, documentation, logs or tests. API resource names remain generic and backward-compatible with the specification. Example project names such as `SimulationPlatform` are *analyzed user projects*, not the product name.

### Final technology selections

| Concern | Decision |
|---|---|
| Backend | Python >=3.12, FastAPI, Pydantic v2 |
| Frontend | React, TypeScript, Cytoscape.js |
| Storage | SQLite with foreign keys, WAL and Alembic migrations |
| Build model | CMake File API codemodel v2; optional Graphviz output for cross-checks |
| C++ semantics | clang-uml JSON first, custom Clang LibTooling later |
| Agent integration | MCP using an open-source Python SDK |
| AI execution | External agent, local-model compatible; no built-in proprietary dependency |
| Tests | pytest, CTest, Playwright; Windows and Linux CI |
| Package management | Python `uv` or standards-compliant pip; Node/npm for frontend |
| Deployment | Local workstation first; cross-platform from day one |

The technology choices do not imply a requirement for a dedicated graph database. Start with indexed SQLite adjacency queries. Do not implement the frontend before the data model and queries work.

## 2. System architecture

```text
React + TypeScript + Cytoscape.js
        | REST /api/v1
FastAPI (request validation, jobs, graph queries)
        | shared service layer
        +---- Analysis orchestrator ---- CMake File API adapter
        |                           \--- clang-uml adapter (M3)
        +---- Architecture query service ---- SQLite snapshot repository
        |
MCP server (M4) ---- same architecture query service
        |
External AI agent (OpenCode / MCP client) ---- local LLM
        |
Approved isolated Git worktree refactoring workflow (M5)
```

**Separation of concerns:** analyzer adapters emit normalized graph observations; the repository validates and persists; query service performs traversal and cycle detection; API and MCP expose the same service; UI renders bounded subgraphs. AI interprets evidence but never becomes the source of structural truth.

## 3. Complete functional requirements

Priorities: **M** = Must, **S** = Should. Must requirements remain product requirements even if assigned to a later milestone.

### FR-01: Discovery and indexing

| ID | Priority | Requirement |
|---|---|---|
| FR-001 | M | Import existing CMake projects. |
| FR-002 | M | Support multi-directory, multi-target CMake projects. |
| FR-003 | M | Parse C++ with Clang-based tooling. |
| FR-004 | M | Identify CMake targets and dependencies. |
| FR-005 | M | Index namespaces, classes, functions, methods and files. |
| FR-006 | M | Support incremental indexing after source changes. |
| FR-007 | M | Honor compilation definitions, include paths and C++ standard. |
| FR-008 | S | Support multiple CMake configurations and presets. |
| FR-009 | S | Distinguish internal and third-party dependencies. |
| FR-010 | S | Support Conan dependency metadata. |

### FR-02: Visualization

| ID | Priority | Requirement |
|---|---|---|
| FR-011 | M | Visualize CMake target dependencies. |
| FR-012 | M | Visualize namespace/package dependencies. |
| FR-013 | M | Visualize class relationships. |
| FR-014 | M | Visualize inheritance and composition. |
| FR-015 | S | Visualize function and method call graphs. |
| FR-016 | M | Support interactive zoom, pan, search and filtering. |
| FR-017 | M | Navigate from graph elements to source code. |
| FR-018 | M | Expand/collapse architectural hierarchy. |
| FR-019 | M | Highlight circular dependencies. |
| FR-020 | S | Export SVG, PNG, Mermaid or PlantUML diagrams. |
| FR-021 | S | Visualize dependency changes between Git revisions. |
| FR-022 | S | Allow custom architectural views. |

### FR-03: Architecture analysis

| ID | Priority | Requirement |
|---|---|---|
| FR-023 | M | Detect circular target/package dependencies. |
| FR-024 | M | Identify highly coupled components. |
| FR-025 | M | Analyze incoming/outgoing dependencies. |
| FR-026 | S | Identify unused dependencies, subject to sufficient evidence. |
| FR-027 | S | Detect layering violations. |
| FR-028 | S | Calculate coupling and cohesion metrics. |
| FR-029 | S | Identify problematic classes/modules. |
| FR-030 | M | Estimate change impact for classes/interfaces. |
| FR-031 | S | Identify interface extraction/component splitting opportunities. |
| FR-032 | S | Support configurable architecture rules. |

### FR-04: AI code understanding

| ID | Priority | Requirement |
|---|---|---|
| FR-033 | M | Ask natural-language questions about codebase. |
| FR-034 | M | Retrieve relevant code and structural relationships. |
| FR-035 | M | Explain class/package responsibilities. |
| FR-036 | M | Explain why components depend on each other. |
| FR-037 | M | Identify architectural weaknesses. |
| FR-038 | M | Suggest refactoring opportunities. |
| FR-039 | M | Cite source references for AI findings. |
| FR-040 | M | Support locally hosted LLMs. |
| FR-041 | M | Support multiple agents via MCP. |
| FR-042 | M | Support architecture-aware context retrieval. |
| FR-043 | S | Configurable prompts and analysis workflows. |

### FR-05: Guided refactoring

| ID | Priority | Requirement |
|---|---|---|
| FR-044 | M | Generate refactoring proposals. |
| FR-045 | M | Estimate affected classes, targets and files before changes. |
| FR-046 | M | Present plans for developer approval. |
| FR-047 | M | Support multi-file refactoring. |
| FR-048 | M | Apply changes in small reviewable steps. |
| FR-049 | M | Track changes with Git. |
| FR-050 | M | Execute builds/tests after changes. |
| FR-051 | S | Compare before/after architecture. |
| FR-052 | M | Detect newly introduced dependency cycles. |
| FR-053 | M | Roll back via Git. |
| FR-054 | S | Support semi-automated refactoring workflows. |

### FR-06: Extensibility and integration

| ID | Priority | Requirement |
|---|---|---|
| FR-055 | M | Provide MCP architecture-query server. |
| FR-056 | M | Provide documented structural query API. |
| FR-057 | M | Integrate with existing AI coding agents. |
| FR-058 | S | IDE integration (VS Code, CLion, etc.). |
| FR-059 | M | Provide CLI for automation. |
| FR-060 | S | CI/CD integration. |
| FR-061 | S | Custom analysis plugins. |
| FR-062 | S | Export JSON/GraphML architecture data. |

### FR-07: Interactive dependency investigation

| ID | Priority | Requirement |
|---|---|---|
| FR-063 | M | Select dependency edges in the UI. |
| FR-064 | M | Send selected nodes, edge type, configuration and Git revision to AI. |
| FR-065 | M | Trace dependency causes to CMake declarations, includes, symbol references or calls where applicable. |
| FR-066 | M | Display concrete source evidence per dependency. |
| FR-067 | M | Ask contextual natural-language questions about selected relationship. |
| FR-068 | M | Propose alternatives to remove/reduce dependency. |
| FR-069 | M | Estimate impact, complexity and risks of alternatives. |
| FR-070 | S | Preview expected graph changes for proposed refactoring. |
| FR-071 | M | Generate detailed plan for selected alternative. |
| FR-072 | M | Retain edge selection context across follow-ups. |
| FR-073 | M | Distinguish direct, transitive and inferred relationships. |
| FR-074 | M | Explicitly state when dependency cannot be conclusively traced. |

## 4. UC-001: Investigate and remove a dependency

**Actor:** software architect. **Preconditions:** an indexed snapshot and dependency graph exist.

1. Select an edge, e.g. `SimulationCore -> QtWidgets`.
2. Display edge type, endpoints, direct/transitive classification, build configuration, revision, and available evidence.
3. Ask: "Where is this dependency coming from?"
4. Query exact edge evidence and contributing paths; explain CMake declarations, includes and semantic uses, with source references. Identify missing or inconclusive evidence.
5. Ask: "How could I get rid of this dependency?"
6. Present alternative strategies (move GUI adapter, invert dependency, extract interface, split target, etc.), impact, trade-offs, affected targets/files and estimated risk.
7. Let the architect approve one plan. Apply in isolated Git worktree in small steps, then build, test and reindex.
8. Compare old/new graph: verify selected dependency is removed (or explicitly report not removed), identify relocated/new dependencies and cycles.

**Acceptance:** edge selection binds all follow-up questions to `{project_id, snapshot_id, edge_id, source_id, target_id, relationship}` until changed or cleared. The AI must cite evidence and distinguish a removed dependency from a merely relocated dependency. No code change without explicit approval.

## 5. Non-functional requirements

| ID | Requirement / initial target |
|---|---|
| NFR-001 | Support at least 2M LOC overall. |
| NFR-002 | Incremental reindexing of affected translation units (later milestone). |
| NFR-003 | Typical structural queries under 2 seconds at product scale; M1 synthetic direct query p95 <200 ms. |
| NFR-004 | Interactive visualization of thousands of visible nodes using scoped/lazy subgraphs. |
| NFR-005 | Fully offline operation, no mandatory external services. |
| NFR-006 | Source code stays local unless user explicitly configures a remote model. |
| NFR-007 | All required components FOSS; maintain license inventory. |
| NFR-008 | Failed analyses never corrupt completed snapshots. |
| NFR-009 | Reproducibility: record Git revision, CMake configuration, tool versions and build context. |
| NFR-010 | Modular analyzer, repository, query, UI and MCP boundaries. |
| NFR-011 | Distinguish verified facts, derived conclusions, AI hypotheses and unknowns. |
| NFR-012 | Configurable CPU, memory and indexing concurrency. |

**M1 benchmark targets:** >=1,000 synthetic CMake targets; direct dependency query p95 <200 ms; SCC detection <5 seconds for 10k nodes/50k edges; <2 GB process memory for synthetic graph test. Benchmark on a documented machine with warm cache. CMake configuration time and graph import time are measured separately. These are initial targets to verify, not claims of achieved performance.

## 6. Graph semantics and identity

### Node kinds

`PROJECT`, `CMAKE_TARGET`, `PACKAGE`, `NAMESPACE`, `CLASS`, `STRUCT`, `FUNCTION`, `METHOD`, `FILE`, `EXTERNAL_LIBRARY`.

M1 implements `PROJECT`, `CMAKE_TARGET`, `FILE`, and `EXTERNAL_LIBRARY` where resolvable.

### Edge kinds

`CONTAINS`, `OWNS_FILE`, `LINKS_TO`, `BUILD_DEPENDS_ON`, `INCLUDES`, `USES_TYPE`, `INHERITS`, `CALLS`, `IMPLEMENTS`, `DEPENDS_ON`.

M1 implements `CONTAINS`, `OWNS_FILE`, `LINKS_TO` when link evidence is actually available, and `BUILD_DEPENDS_ON` for codemodel dependencies. Do **not** simply map all codemodel `dependencies` to `LINKS_TO`.

- Directed `A -> B` means A depends on B, except containment/ownership edges, whose direction is parent -> child.
- `origin`: `declared`, `semantic`, `derived`.
- Multiple evidence observations can support one edge.
- Derived/transitive edges must identify supporting paths and must not be confused with direct declarations.
- `confidence`/verification states should include `verified`, `derived`, `unresolved` where applicable.
- Cross-snapshot identity: `stable_key = kind + canonical logical identity`, never absolute path alone. Use CMake target identity with target name, owning CMake project and collision-safe qualifiers; store CMake codemodel ID separately as snapshot metadata.
- CMake generator expressions, alias targets, imported targets, interface libraries and external link fragments must be handled conservatively. Unknown identities become diagnostics or unresolved references, not invented target nodes.
- Source paths should be repository-relative POSIX-style where possible; keep absolute machine-local paths in snapshot metadata.
- Separate snapshots for distinct configurations and platforms. Do not merge mutually exclusive preprocessor/build configurations into one unqualified graph.

### SQLite DDL (M1 baseline)

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  root_path TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE snapshots (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  git_commit TEXT,
  cmake_config TEXT NOT NULL,
  build_directory TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('building','complete','failed')),
  created_at TEXT NOT NULL
);
CREATE TABLE nodes (
  id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
  kind TEXT NOT NULL,
  name TEXT NOT NULL,
  qualified_name TEXT,
  stable_key TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE(snapshot_id, stable_key),
  UNIQUE(snapshot_id, id)
);
CREATE TABLE edges (
  id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
  source_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  origin TEXT NOT NULL CHECK(origin IN ('declared','semantic','derived')),
  metadata_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE(snapshot_id, id),
  FOREIGN KEY(snapshot_id, source_id) REFERENCES nodes(snapshot_id, id),
  FOREIGN KEY(snapshot_id, target_id) REFERENCES nodes(snapshot_id, id)
);
CREATE TABLE evidence (
  id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL,
  edge_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  file_path TEXT,
  line_start INTEGER,
  line_end INTEGER,
  description TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  FOREIGN KEY(snapshot_id, edge_id) REFERENCES edges(snapshot_id, id)
);
CREATE INDEX idx_nodes_snapshot_kind ON nodes(snapshot_id,kind);
CREATE INDEX idx_edges_source ON edges(snapshot_id,source_id,kind);
CREATE INDEX idx_edges_target ON edges(snapshot_id,target_id,kind);
CREATE INDEX idx_evidence_edge ON evidence(snapshot_id,edge_id);
```

**Migration notes:** manage DDL through Alembic; configure WAL once on initialization rather than relying on transaction-level PRAGMAs. Add CHECKs and indexes where test evidence justifies them. Keep snapshot IDs as UUIDs and entity IDs deterministic within a snapshot or stored UUIDs, with uniqueness enforced by stable keys. Do not expose database implementation in public API.

### Example evidence object

```json
{
  "edge_id": "edge-123",
  "kind": "LINKS_TO",
  "source": "SimulationCore",
  "target": "MathLibrary",
  "origin": "declared",
  "evidence": [{
    "kind": "cmake_link",
    "file": "src/simulation/CMakeLists.txt",
    "line_start": 42,
    "line_end": 42,
    "visibility": "PRIVATE",
    "confidence": "verified"
  }]
}
```

This is a *desired output example*, not a guarantee that the CMake File API exposes an exact link-declaration line. If it cannot be established, return `null` for lines and an explanatory diagnostic. A link command backtrace and a codemodel build dependency are distinct kinds of evidence.

### Persistence rules

1. Create a `building` snapshot and stage its observations transactionally.
2. Validate node/edge referential integrity, evidence consistency, and deduplicate observations.
3. Commit and mark `complete` atomically. Never serve partial snapshots as complete.
4. On failure, mark `failed`, preserve diagnostics and leave the last completed snapshot unchanged.
5. Completed snapshots are immutable; reanalysis creates a new snapshot.
6. Use parameterized SQL and SQLite foreign keys on every connection.
7. Support paginated node/edge queries with deterministic ordering.

## 7. CMake extraction contract

Use CMake File API codemodel v2, not a hand-written parser for arbitrary CMake script semantics.

1. Accept an existing configured build directory, or configure a new one after creating a codemodel query file under `.cmake/api/v1/query/`.
2. Find and parse the latest valid File API index and codemodel response.
3. Enumerate configurations, directories, targets, target JSON files, sources, and codemodel dependency IDs.
4. Map target types and source ownership. Account for generated sources and targets present in multiple configurations.
5. Resolve codemodel dependency IDs to target identities; record `BUILD_DEPENDS_ON` edges.
6. Parse link-related codemodel fields and backtrace graphs where available to derive `LINKS_TO` and evidence, but never assert exact `PUBLIC`/`PRIVATE`/`INTERFACE` semantics without reliable metadata. Distinguish fragments, target references and link command provenance.
7. Preserve unresolved external references in diagnostics and/or `EXTERNAL_LIBRARY` nodes only where identity is grounded.
8. Record CMake version, generator, platform, configuration, Git revision (if available), and analysis adapter version.
9. Emit warnings for unsupported or incomplete constructs, including generator-specific compilation database limitations.

**Windows considerations:** support Ninja and Visual Studio generators for target-level extraction. `compile_commands.json` is not universally available across generators and is not required for M1. For later Clang semantic indexing, document a supported Ninja/Clang analysis configuration. Handle drive letters, case differences, symlinks, UTF-8 paths, and process invocation using argument arrays rather than shell strings.

## 8. API contracts

REST is versioned under `/api/v1`, Pydantic v2 validates requests and responses, and FastAPI generates OpenAPI documentation.

| Method | Path | Milestone | Behavior |
|---|---|---|---|
| POST | `/api/v1/projects` | M1 | Register project root. |
| GET | `/api/v1/projects` | M1 | List projects. |
| POST | `/api/v1/projects/{id}/analyses` | M1 | Queue analysis, return 202 and job ID. |
| GET | `/api/v1/analyses/{id}` | M1 | Status, diagnostics, snapshot ID. |
| GET | `/api/v1/projects/{id}/snapshots` | M1 | List completed/failed snapshots with status. |
| GET | `/api/v1/snapshots/{id}/nodes` | M1 | Paginated nodes, filter kind/name. |
| GET | `/api/v1/snapshots/{id}/edges` | M1 | Paginated edges, filter source/target/kind. |
| GET | `/api/v1/snapshots/{id}/cycles` | M1 | Strongly connected components (size >1 or self-loop). |
| GET | `/api/v1/snapshots/{id}/edges/{edge_id}/evidence` | M1 | Evidence list and diagnostics. |
| GET | `/api/v1/snapshots/{id}/subgraph` | M2 | Bounded graph neighborhood. |
| GET | `/api/v1/snapshots/{id}/impact` | M3 | Impact query. |
| POST | `/api/v1/investigations` | M4 | Context-bound dependency investigation. |
| POST | `/api/v1/refactorings` | M5 | Approved refactoring plan/workflow. |

### Example contracts

`POST /api/v1/projects`:

```json
{"name":"SimulationPlatform","root_path":"/workspace/simulation"}
```

Response `201`:

```json
{"id":"project-123","name":"SimulationPlatform","root_path":"/workspace/simulation"}
```

`POST /api/v1/projects/{id}/analyses`:

```json
{"build_directory":"/workspace/simulation/build","configuration":"Debug","analyzers":["cmake"]}
```

Response `202`:

```json
{"analysis_id":"analysis-123","status":"queued","status_url":"/api/v1/analyses/analysis-123"}
```

`GET /api/v1/snapshots/{id}/edges?source_id=node-123&kind=BUILD_DEPENDS_ON`:

```json
{"items":[{"id":"edge-123","source_id":"node-123","target_id":"node-456","kind":"BUILD_DEPENDS_ON","origin":"declared","evidence_count":1}],"next_cursor":null}
```

Error response:

```json
{"error":{"code":"SNAPSHOT_NOT_FOUND","message":"The requested snapshot does not exist.","details":{}}}
```

**Additional rules:** 400/422 for invalid inputs, 404 for unknown resources, 409 for incompatible analysis state, 500 for unexpected failures. Jobs progress `queued -> running -> completed|failed`. Bound page sizes and traversal depth. No raw SQL from clients. Return no data from `building` snapshots except job diagnostics. Source paths are read-only and must not enable traversal outside allowed project roots.

## 9. MCP and AI contracts (M4)

MCP tools:

| Tool | Input | Output |
|---|---|---|
| `list_projects` | none | registered projects |
| `list_targets` | project/snapshot | CMake targets |
| `get_dependencies` | snapshot, node, direction | direct relationships |
| `get_dependency_evidence` | snapshot, edge | verified source evidence |
| `find_dependency_paths` | snapshot, source, target, bounds | direct/transitive paths |
| `detect_cycles` | snapshot, scope | SCCs |
| `explain_dependency_context` | snapshot, edge | evidence bundle, unknowns |
| `get_refactoring_context` | snapshot, edge | affected files/targets, known constraints |

AI context payload:

```json
{
  "project_id":"project-123",
  "snapshot_id":"snapshot-456",
  "edge_id":"edge-789",
  "source_id":"node-123",
  "target_id":"node-456",
  "relationship":"LINKS_TO"
}
```

The agent must separate structural evidence from hypotheses, cite paths/lines only if verified, preserve selected-edge context across turns, and describe alternative refactorings with impact, trade-offs, risks and uncertainty. MCP provides data, not an independently hallucinated graph. Remote-model use must require explicit configuration and warn about source-code disclosure.

## 10. Frontend contract (M2)

React + TypeScript + Cytoscape.js. Views: project/snapshot selector, target dependency graph, expandable package/class drill-down (M3), selected-edge evidence panel, AI conversation panel (M4), refactoring review (M5). Required behavior: pan/zoom, search, filters, graph scope and expansion, highlight cycles, select node or edge, click through to source evidence. Request bounded subgraphs from API; never render the entire 2M LOC architecture at once. Edge selection persists as a typed context object and is passed unchanged to AI investigation tools. Display direct, transitive and derived relationships differently; visibly flag unresolved provenance.

## 11. Guided refactoring safety contract (M5)

1. Generate evidence-grounded alternative plans; present impact, affected files/targets, build configurations, complexity and risks.
2. Require explicit approval before any code edit.
3. Create a dedicated Git worktree/branch, ensure clean baseline and preserve original working tree.
4. Apply reviewable small edits; record diff, actions, tool outputs and validation logs.
5. Run appropriate CMake configure/build, clang-tidy where applicable and CTest. Never claim success if tests were skipped or unavailable.
6. Reindex, compare selected edge and graph changes; detect new cycles and dependency relocation.
7. Allow review, rejection and rollback; never automatically merge.
8. Protect against prompt injection in repository content, arbitrary command execution and unintended network transfer.

## 12. Repository layout

```text
archmind/
├── README.md
├── IMPLEMENTATION_SPEC.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── package.json
├── docs/
│   ├── requirements.md
│   ├── architecture.md
│   ├── graph-schema.md
│   ├── api.md
│   ├── decisions/
│   └── milestones/
│       ├── m1-indexing.md
│       ├── m2-visualization.md
│       ├── m3-cpp-analysis.md
│       ├── m4-ai-integration.md
│       └── m5-refactoring.md
├── src/archmind/
│   ├── domain/{models.py,graph.py,identifiers.py}
│   ├── analyzers/
│   │   ├── base.py
│   │   ├── cmake/{file_api.py,parser.py,normalizer.py}
│   │   └── clang_uml/adapter.py
│   ├── storage/{database.py,repository.py,migrations/}
│   ├── services/{analysis.py,queries.py,cycles.py}
│   ├── api/{app.py,schemas.py,routes/}
│   ├── mcp/server.py
│   └── cli.py
├── frontend/
│   ├── package.json
│   ├── src/{components/,graph/,api/,App.tsx}
│   └── tests/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contracts/
│   └── fixtures/
│       ├── simple-project/
│       ├── cyclic-dependencies/
│       ├── transitive-dependencies/
│       └── external-libraries/
├── scripts/{bootstrap.ps1,bootstrap.sh}
└── .github/workflows/
```

Create only the directories/files needed for the active milestone; later-module paths are an architectural roadmap, not a demand for empty scaffolding.

### Python packaging contract

Use the distribution and import name `archmind`. The `pyproject.toml` must expose the `archmind` CLI command and install packages from `src/archmind`. Example with Typer:

```toml
[project]
name = "archmind"
requires-python = ">=3.12"

[project.scripts]
archmind = "archmind.cli:app"

[tool.setuptools.packages.find]
where = ["src"]
```

The build backend and exact dependency versions should be chosen during M1 and pinned in the lockfile. If the CLI uses a different framework, adapt the callable but keep the command name. REST API examples remain under `/api/v1`; use `ArchMind` in generated OpenAPI title, CLI help, and service logs.

### Analyzer protocol

```python
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class AnalysisContext:
    project_id: str
    project_root: str
    build_directory: str
    configuration: str

@dataclass(frozen=True)
class AnalysisResult:
    nodes: list  # Replace with typed Node model
    edges: list  # Replace with typed Edge model
    evidence: list  # Replace with typed Evidence model
    diagnostics: list  # Replace with typed Diagnostic model

class ArchitectureAnalyzer(Protocol):
    def analyze(self, context: AnalysisContext) -> AnalysisResult: ...
```

Replace placeholder lists with typed Pydantic/dataclass domain models before implementing the adapter. Analyzer outputs are normalized, not raw codemodel JSON.

## 13. Milestones and gates

### M1: CMake architecture index

**In:** project registration, File API discovery/parsing, CMake targets/sources/dependencies, evidence/diagnostics, SQLite immutable snapshots, CLI, REST queries, SCC detection, cross-platform tests.  
**Out:** class/method semantics, React UI, MCP, AI, refactoring.  
**Gate:** all M1 acceptance tests pass on Windows/Linux; reliable source provenance; reproducible setup.

### M2: Interactive architecture explorer

React graph, scoped queries, filtering, search, hierarchy, selected-edge evidence panel, cycle highlighting.  
**Gate:** architect can select a target dependency and inspect evidence.

### M3: C++ semantic analysis

clang-uml JSON adapter, class/namespace/inheritance/type relationships, symbol-level provenance, source-to-target drill-down, groundwork for incremental indexing and LibTooling extension.  
**Gate:** trace a target dependency to contributing C++ symbols where supported; identify incomplete evidence.

### M4: MCP and AI investigation

MCP tools, external OpenCode/local LLM integration, contextual follow-up, grounded dependency explanation, removal strategies and risk analysis.  
**Gate:** UC-001 works through AI-generated refactoring plan without editing source.

### M5: Guided refactoring

Approval workflow, isolated worktrees, reviewable edits, builds/tests, reindexing, before/after graph, rollback.  
**Gate:** an approved refactoring is executed and dependency-removal outcome verified.

## 14. M1 implementation task list

| ID | Task | Output |
|---|---|---|
| M1-01 | Initialize repo, packaging, lint/test tooling and docs | installable CLI package |
| M1-02 | Typed domain models and stable keys | validated graph observation types |
| M1-03 | SQLite schema, Alembic migrations, repository | immutable snapshot persistence |
| M1-04 | File API discovery and codemodel parsing | CMake extraction adapter |
| M1-05 | Normalize targets, sources, edges, evidence | normalized graph |
| M1-06 | Analysis job lifecycle and diagnostics | durable completed/failed snapshots |
| M1-07 | Graph queries, reverse traversal, SCC algorithm | query service |
| M1-08 | FastAPI REST and CLI commands | usable interfaces |
| M1-09 | CMake fixture projects and automated tests | deterministic regression suite |
| M1-10 | Windows/Linux CI and performance checks | cross-platform validation |

**Suggested vertical slice:** fixture CMake project -> File API codemodel -> typed target nodes and `BUILD_DEPENDS_ON` edges -> SQLite snapshot -> CLI `dependencies` -> pytest. Expand to link evidence, API and cycle detection only after the slice passes.

### Suggested CLI

```text
archmind project add --name Demo --root <path>
archmind analyze --project <id> --build-dir <path> --config Debug
archmind targets --snapshot <id>
archmind dependencies --snapshot <id> --target <stable-key> [--reverse]
archmind cycles --snapshot <id>
archmind evidence --snapshot <id> --edge <id>
archmind serve --host 127.0.0.1 --port 8000
```

Use OS-appropriate paths; these are CLI contracts to implement, not currently executable commands.

## 15. M1 acceptance tests

| ID | Scenario | Expected result |
|---|---|---|
| AT-001 | Import valid CMake project | Project and completed snapshot created. |
| AT-002 | Multiple targets | All configured targets represented. |
| AT-003 | Direct dependencies | Correct directed `BUILD_DEPENDS_ON` and verified `LINKS_TO` where available. |
| AT-004 | Source ownership | Sources linked to appropriate targets. |
| AT-005 | Evidence query | Verified provenance returned; unavailable lines `null`. |
| AT-006 | Acyclic graph | No SCC cycles reported. |
| AT-007 | Cyclic graph | Correct SCC cycles reported. |
| AT-008 | Reverse dependencies | Correct incoming relationships. |
| AT-009 | Unchanged reanalysis | Equivalent canonical graph, no duplicate nodes/edges per snapshot. |
| AT-010 | Dependency change | New snapshot reflects change; old snapshot immutable. |
| AT-011 | Malformed File API reply | Controlled failure and diagnostic. |
| AT-012 | Windows/Linux | Equivalent logical graph for equivalent configurations. |
| AT-013 | Unknown snapshot | Structured 404 error. |
| AT-014 | External dependencies | Grounded external references represented; unresolved links reported honestly. |
| AT-015 | Interrupted indexing | Last successful snapshot remains queryable. |
| AT-016 | Large graph | Paginated, deterministic response within benchmark targets. |

### Reference fixture

```text
test-project/
├── CMakeLists.txt
├── app/{CMakeLists.txt,main.cpp}
├── simulation/{CMakeLists.txt,simulation.cpp}
├── physics/{CMakeLists.txt,physics.cpp}
└── math/{CMakeLists.txt,math.cpp}
```

Fixture intended target links: `Application -> Simulation`, `Simulation -> Physics`, `Simulation -> Math`, `Physics -> Math`. Use separate fixtures for transitive-only relationships, interface targets, external dependencies and cycles. For a cycle fixture, use static libraries and a CMake configuration that permits circular link references; do not create an invalid cycle between unsupported target types. Test the logical `LINKS_TO` relationships separately from codemodel build-order edges.

### Test pseudocode

```python
def test_direct_links(indexed_reference_project):
    graph = indexed_reference_project
    simulation = graph.get_node(kind="CMAKE_TARGET", name="Simulation")
    links = graph.get_dependencies(simulation.id, kind="LINKS_TO", transitive=False)
    assert {node.name for node in links} == {"Physics", "Math"}


def test_snapshot_immutability(indexed_reference_project):
    graph = indexed_reference_project
    old = graph.current_snapshot()
    graph.remove_fixture_dependency("Simulation", "Math")
    new = graph.reanalyze()
    assert old.id != new.id
    assert graph.has_dependency(old.id, "Simulation", "Math")
    assert not graph.has_dependency(new.id, "Simulation", "Math")
```

The fixture methods above are test-harness interfaces to implement, not existing functions.

### M1 Definition of Done

- AT-001 through AT-016 pass in Windows and Linux CI.
- Real CMake File API codemodel fixtures are tested (not only mocked JSON).
- No fabricated `LINKS_TO` edges, link visibility, or source locations.
- CLI and REST expose target dependencies, reverse dependencies, cycles and evidence.
- Completed snapshots immutable; errors are diagnostic and non-destructive.
- Pagination, input validation, basic local security and OpenAPI documentation work.
- README documents install, fixture analysis, querying and known limitations.
- Dependency licenses are checked and reproducible lockfiles are committed.

## 16. Implementation decisions and edge cases to record

Before coding beyond the first vertical slice, create ADRs for:

1. **Identity:** target stable keys across platforms, generators, configurations, alias/imported targets.
2. **Link semantics:** precise distinction between CMake File API dependency entries, link fragments and `target_link_libraries` visibility; evidence limitations.
3. **Snapshot lifecycle:** whether analysis jobs are persisted separately from snapshots (recommended: separate job table for queued/running status).
4. **Source ownership:** a source file can belong to multiple targets; model multiple `OWNS_FILE` edges.
5. **Graph algorithms:** Tarjan or Kosaraju SCC, explicit self-loop handling, bounded path enumeration.
6. **Paths and security:** allowed repository roots, symlinks, Windows path canonicalization, local-only API defaults.
7. **Reproducibility:** record tool versions, environment, generator and configuration without leaking secrets.
8. **License compliance:** audit transitive dependencies and distribute SPDX/license notices as appropriate.

### Important refinements to the baseline

- CMake File API codemodel target `dependencies` are *not* automatically direct link dependencies. Build graph and link graph are distinct. Use separate edge kinds and tests.
- `LINKS_TO` source provenance and `PUBLIC`/`PRIVATE`/`INTERFACE` visibility are not always fully reconstructible from codemodel replies. Store unknowns honestly; later augment with dedicated analysis if needed.
- Immutable snapshots require a publication boundary. A separate analysis-jobs table is preferable to overloading snapshot status with queue state.
- SQLite WAL helps concurrent readers but does not make SQLite a multi-writer graph service. Serialize writes and scope transactions.
- Strict FOSS includes the AI agent, inference server and graph visualization runtime. The project must not require proprietary model APIs.

## 17. README requirements

Create `README.md` at the repository root with the official name **ArchMind**, tagline, status, supported platforms, features grouped by milestone (clearly mark unimplemented features as planned), prerequisites, install and bootstrap steps, commands for analyzing a sample CMake project, REST API usage, test commands, security/privacy assumptions, FOSS licensing status and a link to this specification. The README must not imply planned features are already implemented. The starter README accompanying this handoff is a template; update it as real commands and versions become available.

## 18. Agent execution checklist

1. Read this entire specification and create a concise M1 plan mapped to M1-01..M1-10.
2. Initialize the repository and write ADRs for any material ambiguity.
3. Implement the minimal CMake fixture and verify CMake File API output on the current OS.
4. Implement domain types, SQLite migrations, adapter and query service.
5. Add the CLI vertical slice and tests; run them and report results.
6. Implement analysis job orchestration, REST endpoints, diagnostics and pagination.
7. Add cycle detection, failure isolation, external dependency cases and benchmark tests.
8. Run Windows and Linux CI; do not claim cross-platform completion until both pass.
9. Document limitations, deviations and follow-on tasks for M2.
10. Stop at the M1 gate unless instructed to proceed to later milestones.

**Expected handoff report:** implemented tasks, changed files, commands run, passing/failing tests, benchmark environment/results, known limitations, and remaining blockers. Avoid declaring completion on the basis of code generation alone.

---

**End of implementation specification.**
