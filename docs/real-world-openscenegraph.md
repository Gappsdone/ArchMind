# OpenSceneGraph real-world indexing check

ArchMind was exercised against the upstream [OpenSceneGraph](https://github.com/openscenegraph/OpenSceneGraph) checkout at commit `8cead3e3340e521726127e1c7aa802c1a37b6214` on Linux x86-64. This is a CMake File API and architecture-query validation, **not** an OpenSceneGraph binary build or a C++ semantic-indexing test.

## Reproduce

This host needed the FOSS OpenGL development packages `libgl1-mesa-dev` and `libglu1-mesa-dev` for OpenSceneGraph's CMake generation. The following commands assume those prerequisites, CMake, a C++ compiler and an installed ArchMind CLI. Run them from the ArchMind repository root:

```sh
git clone --depth 1 --filter=blob:none https://github.com/openscenegraph/OpenSceneGraph.git osg
git -C osg fetch --depth 1 origin 8cead3e3340e521726127e1c7aa802c1a37b6214
git -C osg checkout --detach FETCH_HEAD
mkdir -p osg/build-archmind/.cmake/api/v1/query
touch osg/build-archmind/.cmake/api/v1/query/codemodel-v2
cmake -S osg -B osg/build-archmind -G 'Unix Makefiles' -DCMAKE_BUILD_TYPE=Release -DBUILD_OSG_EXAMPLES=OFF -DBUILD_DOCUMENTATION=OFF
export ARCHMIND_DB="$PWD/osg/archmind.db"
PROJECT_ID=$(archmind project add --name OpenSceneGraph --root osg | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
SNAPSHOT_ID=$(archmind analyze --project "$PROJECT_ID" --build-dir osg/build-archmind --config Release | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
archmind dependencies --snapshot "$SNAPSHOT_ID" --target 'CMAKE_TARGET:osgViewer:src/osgViewer' --kind LINKS_TO
archmind cycles --snapshot "$SNAPSHOT_ID" --kind LINKS_TO
```

OpenSceneGraph sets a `Release` CMake configuration even when no `CMAKE_BUILD_TYPE` is passed. ArchMind must therefore receive `--config Release`; an empty configuration is correctly rejected. Use a separate build directory and snapshot for other configurations.

## Observed result

Environment: Debian Linux, Python 3.13.5, CMake 3.31.6, 4 logical CPUs (Intel Core i5-7200U), 8 GiB RAM. OpenSceneGraph was configured with its default plugin and application options, examples/documentation disabled. Optional image/video/toolkit dependencies were absent, so the configured target set is not a full-featured OpenSceneGraph build.

| Check | Result |
|---|---:|
| Configured CMake targets | 104 |
| Source-file nodes / ownership edges | 2,428 / 2,428 |
| Build-order edges | 536 |
| Evidenced local link edges | 485 |
| Unresolved linker-fragment diagnostics | 546 |
| `osgViewer` direct local link edges | 6 (`OpenThreads`, `osg`, `osgDB`, `osgGA`, `osgText`, `osgUtil`) |
| Build-order / link strongly connected components | 0 / 0 |
| Warm direct-link query p95, 50 calls | 13.4 ms |
| CMake graph import via CLI, wall time | 1.47 s |

The tested `osgViewer -> osg` link has File API evidence at `CMakeModules/OsgMacroUtils.cmake:54`, with the owning macro invocation at `src/osgViewer/CMakeLists.txt:280`. The selected-edge REST context returned HTTP 200 and retained the `Release` configuration and Git commit. Reverse-link lookup, bounded overview pagination, CLI dependency/cycle commands and both build-order/link cycle queries were exercised. The older pre-fix snapshot remained queryable and unchanged.

The initial run exposed a real extractor gap: OpenSceneGraph's linker fragments use versioned `.so` filenames while its codemodel artifacts name the unversioned symlinks, and its direct link commands live inside CMake macros. ArchMind had therefore produced zero `LINKS_TO` edges. The extractor now resolves numeric ELF `.so` versions only against known artifact paths **and** codemodel dependency IDs, and recognizes a macro link only when its backtrace roots in the owning target's `CMakeLists.txt`. This avoids treating inherited or unrelated linker fragments as direct declarations. A real-CMake regression test covers the versioned-library/macro case.

The remaining unresolved linker fragments include system libraries and linker flags; ArchMind does not invent external target identities or CMake link visibility for them. A full OpenSceneGraph build, `clang-uml` semantic indexing, a browser walkthrough of this snapshot, and live local-model/OpenCode conversations were not performed in this check.
