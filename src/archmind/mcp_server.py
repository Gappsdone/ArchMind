"""Local stdio MCP interface to the shared, read-only architecture service."""

import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from .core import Store
from .query_service import ArchitectureQueries


def create_mcp_server(database: Path | None = None) -> MCPServer:
    queries = ArchitectureQueries(Store(database or Path(os.getenv("ARCHMIND_DB", "archmind.db"))))
    server = MCPServer("ArchMind")

    @server.tool()
    def list_projects() -> list[dict]:
        """List locally registered CMake projects."""
        return queries.list_projects()

    @server.tool()
    def list_targets(
        snapshot_id: str, project_id: str | None = None, cursor: str | None = None, limit: int = 100
    ) -> dict:
        """List CMake targets in a completed snapshot, with a bounded page."""
        return queries.list_targets(snapshot_id, project_id, cursor, limit)

    @server.tool()
    def get_dependencies(
        snapshot_id: str,
        node_id: str,
        direction: str = "outgoing",
        kind: str | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict:
        """Get direct graph edges; BUILD_DEPENDS_ON does not imply a linker relationship."""
        return queries.get_dependencies(snapshot_id, node_id, direction, kind, cursor, limit)

    @server.tool()
    def get_dependency_evidence(snapshot_id: str, edge_id: str) -> dict:
        """Get source evidence and diagnostics for one direct edge."""
        return queries.get_dependency_evidence(snapshot_id, edge_id)

    @server.tool()
    def find_dependency_paths(
        snapshot_id: str,
        source_id: str,
        target_id: str,
        max_depth: int = 4,
        max_paths: int = 10,
        kind: str | None = None,
    ) -> dict:
        """Find bounded target dependency paths, explicitly labeling transitive paths."""
        return queries.find_dependency_paths(
            snapshot_id, source_id, target_id, max_depth, max_paths, kind
        )

    @server.tool()
    def detect_cycles(snapshot_id: str, kind: str = "BUILD_DEPENDS_ON") -> dict:
        """Detect strongly connected components for one relationship kind."""
        return queries.detect_cycles(snapshot_id, kind)

    @server.tool()
    def explain_dependency_context(snapshot_id: str, edge_id: str) -> dict:
        """Return the selected edge's grounded evidence and explicit unknowns."""
        return queries.explain_dependency_context(snapshot_id, edge_id)

    @server.tool()
    def get_refactoring_context(snapshot_id: str, edge_id: str) -> dict:
        """Return read-only affected targets/files and known constraints for planning."""
        return queries.get_refactoring_context(snapshot_id, edge_id)

    return server
