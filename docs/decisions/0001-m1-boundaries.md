# ADR 0001: M1 graph boundaries

Status: Accepted for M1 (2026-11-17)

- Identity: target stable key combines kind, CMake target name and owning source directory; codemodel ID is snapshot metadata. Aliases and imported targets without a grounded codemodel identity are not invented.
- Build vs link: every codemodel dependency is `BUILD_DEPENDS_ON`. `LINKS_TO` requires an artifact-matched linker fragment plus a local `target_link_libraries` backtrace. Static libraries often have no link fragments, so their logical links may remain unreported. Link visibility is unknown.
- Jobs/snapshots: separate persistent job and snapshot records. Publication of graph records and `complete` status uses one transaction; failed snapshots preserve diagnostics.
- Ownership: one FILE node may have multiple `OWNS_FILE` edges.
- Algorithms: iterative Kosaraju SCC includes self-loops and avoids Python recursion limits.
- Paths: project roots are resolved on registration; build directories must stay inside root. Source paths from File API are read-only metadata. Service listens on loopback by default.
- Reproducibility: capture CMake version, generator, configuration, Git commit when present, and adapter version; do not persist environment variables.
- License: required runtime and development packages are FOSS. Project license was approved as Apache-2.0 on 2026-11-17. A release must include a full transitive SPDX audit.

## Known M1 deviations and next work

The File API cannot reliably recover all static-library link declarations, imported/external library identities, visibility, or source lines. A future structured CMake trace adapter could supplement it. CMake may collapse static-library link cycles in its build-order graph. REST jobs currently use FastAPI background tasks; process interruption can leave a `running` job and `building` snapshot, though the last complete snapshot remains available. A production job worker should recover interrupted records on startup. Cross-platform CI is configured but has not yet run on Windows.
