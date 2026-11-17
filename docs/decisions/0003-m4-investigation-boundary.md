# ADR 0003: M4 investigation and model boundary

Status: Accepted for M4 (2026-11-17).

- The official MIT-licensed Python MCP SDK provides a stdio server only. OpenCode or another MCP client launches it locally; ArchMind does not own the agent runtime.
- MCP and REST investigations call the same read-only `ArchitectureQueries` service. Neither accesses SQLite with user-provided SQL.
- An investigation stores an immutable six-field selected-edge identity and append-only user/assistant turns in SQLite. The selected edge is revalidated against a completed snapshot before creation. Follow-ups use the investigation ID, not a mutable edge selection in a prompt.
- The optional direct model bridge uses OpenAI-compatible chat completions. Endpoints default to loopback; remote endpoints require an explicit environment opt-in. No vendor API is required. The model receives bounded architecture metadata, not arbitrary source snippets.
- The model returns structured proposals. Citation IDs are validated and ungrounded claims are demoted to hypotheses; affected files/targets are filtered to indexed entities. Citation-linked prose still needs human review because a valid citation cannot prove that the model interpreted it correctly.
- M4 never applies edits, runs proposal commands or approves refactoring. Those actions are M5.

Consequences: local clients can choose their own FOSS model, while the built-in UI is usable with a configured local endpoint. Model quality and live OpenCode interoperability remain separate deployment checks.
