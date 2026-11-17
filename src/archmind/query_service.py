"""Shared read-only architecture queries for REST, MCP and investigations."""

import json
from collections import deque

from .core import NotFound, Store

TARGET_RELATIONSHIPS = {"BUILD_DEPENDS_ON", "LINKS_TO"}
CYCLE_KINDS = {"BUILD_DEPENDS_ON", "LINKS_TO", "INHERITS", "USES_TYPE", "DEPENDS_ON"}


class ArchitectureQueries:
    def __init__(self, store: Store):
        self.store = store

    def list_projects(self) -> list[dict]:
        return self.store.projects()

    def list_targets(
        self,
        snapshot_id: str,
        project_id: str | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict:
        snapshot = self.store.snapshot_detail(snapshot_id)
        if project_id is not None and snapshot["project_id"] != project_id:
            raise NotFound("Snapshot does not belong to project")
        if not 1 <= limit <= 500:
            raise ValueError("Target page size outside supported bounds")
        return self.store.nodes(snapshot_id, kind="CMAKE_TARGET", cursor=cursor, limit=limit)

    def get_dependencies(
        self,
        snapshot_id: str,
        node_id: str,
        direction: str = "outgoing",
        kind: str | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict:
        self.store.node_detail(snapshot_id, node_id)
        if direction not in ("outgoing", "incoming") or not 1 <= limit <= 500:
            raise ValueError("Invalid direction or page size")
        return self.store.edges(
            snapshot_id,
            source_id=node_id if direction == "outgoing" else None,
            target_id=node_id if direction == "incoming" else None,
            kind=kind,
            cursor=cursor,
            limit=limit,
        )

    def get_dependency_evidence(self, snapshot_id: str, edge_id: str) -> dict:
        return self.store.evidence(snapshot_id, edge_id)

    def find_dependency_paths(
        self,
        snapshot_id: str,
        source_id: str,
        target_id: str,
        max_depth: int = 4,
        max_paths: int = 10,
        kind: str | None = None,
    ) -> dict:
        if not 1 <= max_depth <= 6 or not 1 <= max_paths <= 20:
            raise ValueError("Path bounds outside supported range")
        if kind is not None and kind not in TARGET_RELATIONSHIPS:
            raise ValueError("Unsupported target dependency kind")
        for node_id in (source_id, target_id):
            if self.store.node_detail(snapshot_id, node_id)["kind"] != "CMAKE_TARGET":
                raise ValueError("Dependency paths require CMake targets")
        if source_id == target_id:
            return {
                "items": [],
                "truncated": False,
                "diagnostics": ["Use cycle detection for self-dependencies"],
            }
        with self.store.connect() as db:
            self.store._snapshot(db, snapshot_id)
            where = "e.kind=?" if kind else "e.kind IN ('BUILD_DEPENDS_ON','LINKS_TO')"
            args = (snapshot_id, kind) if kind else (snapshot_id,)
            rows = db.execute(
                f"SELECT e.id,e.source_id,e.target_id,e.kind FROM edges e "
                f"WHERE e.snapshot_id=? AND {where} ORDER BY e.id",
                args,
            ).fetchall()
        adjacency: dict[str, list[dict]] = {}
        for row in rows:
            adjacency.setdefault(row["source_id"], []).append(dict(row))
        queue = deque([(source_id, (source_id,), ())])
        results = []
        expansions = 0
        truncated = False
        while queue:
            node_id, nodes, edges = queue.popleft()
            if len(edges) >= max_depth:
                continue
            for edge in adjacency.get(node_id, []):
                next_id = edge["target_id"]
                if next_id in nodes:
                    continue
                next_nodes = (*nodes, next_id)
                next_edges = (*edges, {"id": edge["id"], "kind": edge["kind"]})
                if next_id == target_id:
                    results.append(
                        {
                            "node_ids": list(next_nodes),
                            "edges": list(next_edges),
                            "hops": len(next_edges),
                            "classification": "one_graph_edge"
                            if len(next_edges) == 1
                            else "transitive_path",
                        }
                    )
                    if len(results) >= max_paths:
                        return {"items": results, "truncated": True, "diagnostics": []}
                else:
                    queue.append((next_id, next_nodes, next_edges))
                expansions += 1
                if expansions >= 20_000:
                    truncated = True
                    return {
                        "items": results,
                        "truncated": truncated,
                        "diagnostics": ["Path enumeration stopped at the work bound"],
                    }
        return {"items": results, "truncated": truncated, "diagnostics": []}

    def detect_cycles(self, snapshot_id: str, kind: str = "BUILD_DEPENDS_ON") -> dict:
        if kind not in CYCLE_KINDS:
            raise ValueError("Unsupported cycle relationship kind")
        return {"items": self.store.cycles(snapshot_id, kind)}

    def explain_dependency_context(self, snapshot_id: str, edge_id: str) -> dict:
        snapshot = self.store.snapshot_detail(snapshot_id)
        edge = self.store.evidence(snapshot_id, edge_id)
        source = self.store.node_detail(snapshot_id, edge["source_id"])
        target = self.store.node_detail(snapshot_id, edge["target_id"])
        evidence = []
        unknowns = []
        for item in edge["evidence"]:
            metadata = json.loads(item["metadata_json"])
            record = {
                "id": item["id"],
                "kind": item["kind"],
                "file_path": item["file_path"],
                "line_start": item["line_start"],
                "line_end": item["line_end"],
                "description": item["description"],
                "confidence": metadata.get("confidence", "unresolved"),
            }
            evidence.append(record)
            if item["line_start"] is None:
                unknowns.append(f"Exact source line is unavailable for evidence {item['id']}")
        if not evidence:
            unknowns.append("No edge evidence is available")
        if edge["kind"] == "BUILD_DEPENDS_ON":
            unknowns.append(
                "CMake build-order dependency does not establish a direct linker relationship"
            )
        if edge["kind"] == "LINKS_TO":
            unknowns.append(
                "Link visibility (PUBLIC/PRIVATE/INTERFACE) is not established by this snapshot"
            )
        context = {
            "project_id": snapshot["project_id"],
            "snapshot_id": snapshot_id,
            "edge_id": edge_id,
            "source_id": source["id"],
            "target_id": target["id"],
            "relationship": edge["kind"],
            "origin": edge["origin"],
            "source": {
                "id": source["id"],
                "name": source["name"],
                "stable_key": source["stable_key"],
            },
            "target": {
                "id": target["id"],
                "name": target["name"],
                "stable_key": target["stable_key"],
            },
            "configuration": snapshot["cmake_config"],
            "git_commit": snapshot["git_commit"],
            "evidence": evidence,
            "unknowns": unknowns,
        }
        if edge["kind"] in TARGET_RELATIONSHIPS:
            context["symbol_trace"] = self.store.symbol_trace(snapshot_id, edge_id, limit=20)
            context["paths"] = self.find_dependency_paths(
                snapshot_id,
                source["id"],
                target["id"],
                max_depth=3,
                max_paths=5,
                kind=edge["kind"],
            )
        return context

    def get_refactoring_context(self, snapshot_id: str, edge_id: str) -> dict:
        context = self.explain_dependency_context(snapshot_id, edge_id)
        if context["relationship"] not in TARGET_RELATIONSHIPS:
            return {
                "context": context,
                "affected_targets": [],
                "affected_files": [],
                "known_constraints": [
                    "Target-level refactoring context requires a CMake target edge"
                ],
            }
        affected_targets = [context["source"], context["target"]]
        files = []
        ownership_truncated = False
        for target in affected_targets:
            owned = self.store.edges(
                snapshot_id, source_id=target["id"], kind="OWNS_FILE", limit=100
            )
            ownership_truncated = ownership_truncated or owned["next_cursor"] is not None
            files.extend(
                self.store.node_detail(snapshot_id, item["target_id"])["name"]
                for item in owned["items"]
            )
        incoming = self.store.edges(
            snapshot_id, target_id=context["source_id"], kind="BUILD_DEPENDS_ON", limit=100
        )
        return {
            "context": context,
            "affected_targets": affected_targets,
            "affected_files": sorted(set(files)),
            "incoming_dependents": [item["source_id"] for item in incoming["items"]],
            "truncated": ownership_truncated or incoming["next_cursor"] is not None,
            "known_constraints": context["unknowns"],
        }
