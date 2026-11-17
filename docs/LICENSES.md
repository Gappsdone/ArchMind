# Resolved Python dependency SPDX inventory

Generated from the M1 development environment and `uv.lock` on 2026-11-17 with `pip-licenses`. Runtime and development dependencies are included. License labels were normalized to SPDX where metadata used prose. This inventory does not replace review of license notices for release redistribution. ArchMind itself is licensed Apache-2.0 with owner approval (2026-11-17).

| Package | Pinned version | SPDX license |
|---|---:|---|
| Mako | 1.4.3 | MIT |
| MarkupSafe | 3.0.4 | BSD-3-Clause |
| Pygments | 2.21.0 | BSD-2-Clause |
| SQLAlchemy | 2.1.9 | MIT |
| alembic | 1.20.1 | MIT |
| annotated-doc | 0.0.6 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.16.0 | MIT |
| certifi | 2026.10.23 | MPL-2.0 |
| click | 8.5.1 | BSD-3-Clause |
| fastapi | 0.163.2 | MIT |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| iniconfig | 2.3.1 | MIT |
| markdown-it-py | 4.3.0 | MIT |
| mdurl | 0.1.2 | MIT |
| opentelemetry-api | 1.45.2 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pluggy | 1.7.0 | MIT |
| pydantic | 2.14.3 | MIT |
| pydantic_core | 2.50.4 | MIT |
| pytest | 8.4.2 | MIT |
| rich | 15.0.0 | MIT |
| ruff | 0.17.5 | MIT |
| shellingham | 1.5.4 | ISC |
| starlette | 1.10.0 | BSD-3-Clause |
| typer | 0.29.1 | MIT |
| typing-inspection | 0.4.5 | MIT |
| typing_extensions | 4.16.0 | Python-2.0 |
| uvicorn | 0.54.0 | BSD-3-Clause |

External FOSS tools used during M1: CMake (BSD-3-Clause), Ninja (Apache-2.0), uv (Apache-2.0 OR MIT), Git (GPL-2.0-only). Verify installed tool licenses in target distributions.

## Frontend resolved package licenses

The M2 npm lockfile contains React 19.3.1, React DOM 19.3.1, Cytoscape 3.35.0, esbuild 0.28.2 and associated platform binaries (MIT); TypeScript 5.9.3 and Playwright 1.65.1 (Apache-2.0); and MIT-licensed type packages. See `frontend/package-lock.json` for the full version tree. `npm audit` reported zero advisories on 2026-11-17. The bundled runtime JavaScript contains React, React DOM, scheduler and Cytoscape; their full license notices ship in `src/archmind/web/THIRD_PARTY_NOTICES.txt`.

M3 optional semantic analyzer: clang-uml 0.6.3, Apache-2.0 (external executable, not bundled in the ArchMind wheel). Its LLVM/Clang and yaml-cpp dependencies are FOSS; verify the target platform packages and redistribute applicable notices if packaging the tool.

## M4 additions to the locked dependency set

The M4 Python MCP SDK and its newly resolved dependencies are FOSS. Versions below are from `uv.lock` on 2026-11-17. Windows-only `pywin32` and Pyodide-only `httpx2-jsfetch` were verified from package metadata, not installed on this Linux host.

| Package | SPDX license |
|---|---|
| attrs | MIT |
| cffi | MIT-0 |
| cryptography | Apache-2.0 OR BSD-3-Clause |
| httpcore2, httpx2, httpx2-jsfetch | BSD-3-Clause |
| jsonschema, jsonschema-specifications | MIT |
| mcp, mcp-types | MIT |
| pycparser | BSD-3-Clause |
| pyjwt | MIT |
| python-multipart | Apache-2.0 |
| pywin32 | Python-2.0 |
| referencing, rpds-py | MIT |
| sse-starlette | BSD-3-Clause |
| truststore | MIT |

No built-in model runtime is required. Users can connect a FOSS locally hosted model via the optional OpenAI-compatible HTTP bridge or use an external MCP-capable agent.
