# ADR 0002: clang-uml semantic provenance and ownership

Status: Accepted for the M3 slice (2026-11-17)

clang-uml class-diagram JSON schema v3 is the first semantic adapter. It provides class and method declaration locations, qualified identities, inheritance and typed class relationships, but relationship objects do not carry exact source lines. ArchMind uses a unique labelled member declaration as verified `USES_TYPE` evidence. Otherwise relationship lines are `null` and confidence is `derived`. Class/struct declaration locations are separate facts and cannot be substituted for missing inheritance-clause lines.

CMake File API `OWNS_FILE` edges are the only M3 basis for target ownership. A header absent from a target's codemodel source list is not assigned heuristically by its path or translation unit, since multiple targets can include it. Target-level symbol traces and target impact estimates therefore report incompleteness instead of inventing ownership. Namespace `DEPENDS_ON` edges are derived from class relationships, retain supporting evidence and never become declared dependencies.

Semantic mode requires a compilation database from a Ninja/Makefiles analysis build. The database supplies include paths, definitions and language-standard flags. Its hash is stored for future incremental indexing, but current analysis is full. The adapter runs only a configured local executable with fixed arguments and a temporary generated config; no repository-provided command is executed. Schema changes require an explicit adapter revision rather than silent assumptions.
