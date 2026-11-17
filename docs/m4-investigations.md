# M4: MCP and selected-edge investigations

M4 adds a read-only MCP stdio server, a shared architecture query service, durable investigations bound to an exact completed-snapshot edge, and an opt-in OpenAI-compatible model bridge. It does **not** edit source code, execute model-proposed commands, approve a plan, or claim that a dependency was removed. Those belong to M5.

## MCP with an external coding agent

Set `ARCHMIND_DB` to the database containing completed snapshots and start `archmind mcp`. Configure an MCP-capable client such as OpenCode to launch that command over stdio with the same environment. The server exposes `list_projects`, `list_targets`, `get_dependencies`, `get_dependency_evidence`, `find_dependency_paths`, `detect_cycles`, `explain_dependency_context`, and `get_refactoring_context`. All tools use the same read-only query service as REST investigations. Path enumeration is bounded to six hops, 20 paths and 20,000 expansions; pages are capped at 500. A `BUILD_DEPENDS_ON` edge is build order, **not** proof of a direct link. Use `kind=LINKS_TO` for separately evidenced links.

The external agent is responsible for its own model connection. ArchMind MCP sends architecture metadata requested by the client; review the client's model configuration before sharing proprietary source evidence. No proprietary model/API is required by ArchMind.

## Built-in investigation panel

Select a target relationship in the explorer and use **Explain origin**, **Explore removal**, or a follow-up question. The first question creates a durable investigation carrying exactly `{project_id,snapshot_id,edge_id,source_id,target_id,relationship}`. Follow-ups reuse its ID and prior turns. Changing the selected edge creates a new context. The API rejects a context that does not match the completed snapshot.

To enable responses, configure a locally hosted OpenAI-compatible `/v1/chat/completions` endpoint before starting `archmind serve`:

```sh
export ARCHMIND_MODEL_BASE_URL=http://127.0.0.1:1234/v1
export ARCHMIND_MODEL_NAME=your-local-model-name
archmind serve
```

The URL and model name are examples, not a running service supplied with ArchMind. `ARCHMIND_MODEL_API_KEY` is optional. Remote endpoints are rejected unless `ARCHMIND_ALLOW_REMOTE_MODEL=1`; enabling that flag may disclose architecture metadata to the remote operator. No source snippets are sent by default, only bounded graph/evidence/context records. The service itself binds to loopback by default.

REST: `POST /api/v1/investigations` with the six-field selection object; `GET /api/v1/investigations/{id}` for context and turns; `POST /api/v1/investigations/{id}/messages` with `{"question":"..."}`. `GET /api/v1/snapshots/{id}/edges/{edge_id}/context` exposes the same structural bundle. Unconfigured or malformed model responses return a structured 409, and no user/assistant turn is persisted for a failed model call.

## Grounding and limits

The model receives evidence IDs, source paths/lines when available, uncertainty notes, affected targets/files and prior turns. It is instructed to separate findings from hypotheses and produce proposal-only alternatives including impact, trade-offs, risk, complexity, affected entities and steps. ArchMind validates citation IDs against that edge's evidence, demotes missing/unsupported citations to hypotheses, and filters proposed affected targets/files to indexed entities. A citation-linked AI sentence is still an **interpretation**, not a mechanically verified fact; inspect the evidence panel before accepting it. Unknown source lines remain unknown. M3's incomplete symbol/ownership analysis can limit M4's refactoring context. The API does not fetch arbitrary paths or run generated steps.

A fake local-model transport is covered by automated tests. No real local inference runtime was available in the implementation environment, so live model quality and OpenCode integration still need end-to-end validation on a configured workstation. Windows CI is configured but had not run at this handoff.
