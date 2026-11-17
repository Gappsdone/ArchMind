"""SQLite snapshot repository, analysis service and bounded graph queries."""

import json
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .cmake import extract
from .models import Observation


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, root_path TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), git_commit TEXT, cmake_config TEXT NOT NULL, build_directory TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('building','complete','failed')), created_at TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}', diagnostics_json TEXT NOT NULL DEFAULT '[]');
CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), snapshot_id TEXT REFERENCES snapshots(id), status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed')), diagnostics_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS nodes (id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES snapshots(id), kind TEXT NOT NULL, name TEXT NOT NULL, stable_key TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}', UNIQUE(snapshot_id, stable_key), UNIQUE(snapshot_id, id));
CREATE TABLE IF NOT EXISTS edges (id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES snapshots(id), source_id TEXT NOT NULL, target_id TEXT NOT NULL, kind TEXT NOT NULL, origin TEXT NOT NULL CHECK(origin IN ('declared','semantic','derived')), metadata_json TEXT NOT NULL DEFAULT '{}', UNIQUE(snapshot_id,id), UNIQUE(snapshot_id,source_id,target_id,kind), FOREIGN KEY(snapshot_id,source_id) REFERENCES nodes(snapshot_id,id), FOREIGN KEY(snapshot_id,target_id) REFERENCES nodes(snapshot_id,id));
CREATE TABLE IF NOT EXISTS evidence (id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL, edge_id TEXT NOT NULL, kind TEXT NOT NULL, file_path TEXT, line_start INTEGER, line_end INTEGER, description TEXT, metadata_json TEXT NOT NULL DEFAULT '{}', FOREIGN KEY(snapshot_id,edge_id) REFERENCES edges(snapshot_id,id));
CREATE INDEX IF NOT EXISTS idx_nodes_snapshot_kind ON nodes(snapshot_id,kind);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(snapshot_id,source_id,kind);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(snapshot_id,target_id,kind);
CREATE INDEX IF NOT EXISTS idx_evidence_edge ON evidence(snapshot_id,edge_id);
"""


class NotFound(ValueError):
    pass


class Store:
    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        from alembic import command
        from alembic.config import Config

        config = Config()
        config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
        config.set_main_option("archmind_db_path", str(self.path))
        command.upgrade(config, "head")
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def project_add(self, name: str, root: Path) -> dict:
        root = root.resolve(strict=True)
        if not root.is_dir() or not (root / "CMakeLists.txt").is_file():
            raise ValueError("Project root must be a directory containing CMakeLists.txt")
        record = {"id": _id(), "name": name, "root_path": str(root)}
        with self.connect() as db:
            db.execute("INSERT INTO projects VALUES (?,?,?,?)", (*record.values(), _now()))
        return record

    def projects(self) -> list[dict]:
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute("SELECT id,name,root_path FROM projects ORDER BY name,id")
            ]

    def project(self, project_id: str) -> dict:
        with self.connect() as db:
            row = db.execute(
                "SELECT id,name,root_path FROM projects WHERE id=?", (project_id,)
            ).fetchone()
        if row is None:
            raise NotFound("Project not found")
        return dict(row)

    def analyze(
        self,
        project_id: str,
        build: Path,
        config: str,
        configure: bool = False,
        job_id: str | None = None,
    ) -> dict:
        project = self.project(project_id)
        root = Path(project["root_path"])
        build = build.resolve()
        if build != root and root not in build.parents:
            raise ValueError("Build directory must be inside the project root")
        if not configure and not build.is_dir():
            raise ValueError("Configured build directory does not exist")
        snapshot_id = _id()
        git = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=False,
        )
        commit = git.stdout.strip() if git.returncode == 0 else None
        with self.connect() as db:
            db.execute(
                "INSERT INTO snapshots (id,project_id,git_commit,cmake_config,build_directory,status,created_at) VALUES (?,?,?,?,?,'building',?)",
                (snapshot_id, project_id, commit, config, str(build), _now()),
            )
            if job_id:
                db.execute(
                    "UPDATE jobs SET status='running',snapshot_id=? WHERE id=?",
                    (snapshot_id, job_id),
                )
        try:
            obs, metadata = extract(root, build, config, configure)
            self._publish(snapshot_id, obs, metadata)
            if job_id:
                with self.connect() as db:
                    db.execute("UPDATE jobs SET status='completed' WHERE id=?", (job_id,))
            return {"id": snapshot_id, "status": "complete", "diagnostics": list(obs.diagnostics)}
        except Exception as exc:
            with self.connect() as db:
                db.execute(
                    "UPDATE snapshots SET status='failed',diagnostics_json=? WHERE id=?",
                    (json.dumps([str(exc)]), snapshot_id),
                )
                if job_id:
                    db.execute(
                        "UPDATE jobs SET status='failed',diagnostics_json=? WHERE id=?",
                        (json.dumps([str(exc)]), job_id),
                    )
            raise

    def queue(self, project_id: str) -> str:
        self.project(project_id)
        job_id = _id()
        with self.connect() as db:
            db.execute(
                "INSERT INTO jobs (id,project_id,status,created_at) VALUES (?,?,'queued',?)",
                (job_id, project_id, _now()),
            )
        return job_id

    def job(self, job_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise NotFound("Analysis job not found")
        item = dict(row)
        item["diagnostics"] = json.loads(item.pop("diagnostics_json"))
        return item

    def _publish(self, snapshot_id: str, obs: Observation, metadata: dict) -> None:
        keys = {node.key for node in obs.nodes}
        if len(keys) != len(obs.nodes):
            raise ValueError("Duplicate node key")
        if any(e.source not in keys or e.target not in keys for e in obs.edges):
            raise ValueError("Edge endpoint not present in graph")
        with self.connect() as db:
            for n in obs.nodes:
                db.execute(
                    "INSERT INTO nodes VALUES (?,?,?,?,?,?)",
                    (_id(), snapshot_id, n.kind, n.name, n.key, json.dumps(n.metadata)),
                )
            ids = {
                r["stable_key"]: r["id"]
                for r in db.execute(
                    "SELECT id,stable_key FROM nodes WHERE snapshot_id=?", (snapshot_id,)
                )
            }
            for e in obs.edges:
                edge_id = _id()
                db.execute(
                    "INSERT INTO edges VALUES (?,?,?,?,?,?,?)",
                    (
                        edge_id,
                        snapshot_id,
                        ids[e.source],
                        ids[e.target],
                        e.kind,
                        e.origin,
                        json.dumps(e.metadata),
                    ),
                )
                for v in e.evidence:
                    db.execute(
                        "INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            _id(),
                            snapshot_id,
                            edge_id,
                            v.kind,
                            v.file_path,
                            v.line_start,
                            v.line_start,
                            v.description,
                            json.dumps({"confidence": v.confidence}),
                        ),
                    )
            db.execute(
                "UPDATE snapshots SET status='complete',metadata_json=?,diagnostics_json=? WHERE id=? AND status='building'",
                (json.dumps(metadata), json.dumps(obs.diagnostics), snapshot_id),
            )

    def snapshots(self, project_id: str) -> list[dict]:
        self.project(project_id)
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,project_id,git_commit,cmake_config,build_directory,status,created_at,metadata_json,diagnostics_json FROM snapshots WHERE project_id=? ORDER BY created_at DESC,id DESC",
                    (project_id,),
                )
            ]

    def _snapshot(self, db, snapshot_id: str) -> None:
        row = db.execute("SELECT status FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
        if row is None or row["status"] != "complete":
            raise NotFound("Completed snapshot not found")

    def nodes(
        self,
        snapshot_id: str,
        kind: str | None = None,
        name: str | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict:
        with self.connect() as db:
            self._snapshot(db, snapshot_id)
            where, args = ["snapshot_id=?"], [snapshot_id]
            if kind:
                where.append("kind=?")
                args.append(kind)
            if name:
                where.append("name LIKE ?")
                args.append(f"%{name}%")
            if cursor:
                where.append("stable_key>?")
                args.append(cursor)
            rows = db.execute(
                f"SELECT id,kind,name,stable_key,metadata_json FROM nodes WHERE {' AND '.join(where)} ORDER BY stable_key LIMIT ?",
                (*args, limit + 1),
            ).fetchall()
        items = [dict(row) for row in rows[:limit]]
        return {
            "items": items,
            "next_cursor": items[-1]["stable_key"] if len(rows) > limit else None,
        }

    def node_by_key(self, snapshot_id: str, stable_key: str) -> dict:
        with self.connect() as db:
            self._snapshot(db, snapshot_id)
            row = db.execute(
                "SELECT id,kind,name,stable_key FROM nodes WHERE snapshot_id=? AND stable_key=?",
                (snapshot_id, stable_key),
            ).fetchone()
        if row is None:
            raise NotFound("Node not found")
        return dict(row)

    def edges(
        self,
        snapshot_id: str,
        source_id: str | None = None,
        target_id: str | None = None,
        kind: str | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict:
        with self.connect() as db:
            self._snapshot(db, snapshot_id)
            where, args = ["e.snapshot_id=?"], [snapshot_id]
            for col, value in (("source_id", source_id), ("target_id", target_id), ("kind", kind)):
                if value:
                    where.append(f"e.{col}=?")
                    args.append(value)
            if cursor:
                where.append("e.id>?")
                args.append(cursor)
            rows = db.execute(
                f"SELECT e.id,e.source_id,e.target_id,e.kind,e.origin,e.metadata_json,COUNT(v.id) AS evidence_count FROM edges e LEFT JOIN evidence v ON v.edge_id=e.id WHERE {' AND '.join(where)} GROUP BY e.id ORDER BY e.id LIMIT ?",
                (*args, limit + 1),
            ).fetchall()
        items = [dict(row) for row in rows[:limit]]
        return {"items": items, "next_cursor": items[-1]["id"] if len(rows) > limit else None}

    def evidence(self, snapshot_id: str, edge_id: str) -> dict:
        with self.connect() as db:
            self._snapshot(db, snapshot_id)
            edge = db.execute(
                "SELECT id,source_id,target_id,kind,origin FROM edges WHERE snapshot_id=? AND id=?",
                (snapshot_id, edge_id),
            ).fetchone()
            if edge is None:
                raise NotFound("Edge not found")
            records = [
                dict(r)
                for r in db.execute(
                    "SELECT kind,file_path,line_start,line_end,description,metadata_json FROM evidence WHERE snapshot_id=? AND edge_id=? ORDER BY id",
                    (snapshot_id, edge_id),
                )
            ]
        return {
            **dict(edge),
            "evidence": records,
            "diagnostics": [] if records else ["No source provenance available"],
        }

    def cycles(self, snapshot_id: str, kind: str = "BUILD_DEPENDS_ON") -> list[list[str]]:
        with self.connect() as db:
            self._snapshot(db, snapshot_id)
            pairs = db.execute(
                "SELECT source_id,target_id FROM edges WHERE snapshot_id=? AND kind=?",
                (snapshot_id, kind),
            ).fetchall()
        graph = {}
        for source, target in pairs:
            graph.setdefault(source, []).append(target)
            graph.setdefault(target, [])
        # Iterative Kosaraju avoids recursion limits on large target graphs.
        seen, order = set(), []
        for start in graph:
            if start in seen:
                continue
            seen.add(start)
            stack = [(start, iter(graph[start]))]
            while stack:
                node, children = stack[-1]
                child = next(children, None)
                if child is None:
                    order.append(node)
                    stack.pop()
                elif child not in seen:
                    seen.add(child)
                    stack.append((child, iter(graph[child])))
        reverse = {key: [] for key in graph}
        for source, targets in graph.items():
            for target in targets:
                reverse[target].append(source)
        seen.clear()
        result = []
        for start in reversed(order):
            if start in seen:
                continue
            component, stack = [], [start]
            seen.add(start)
            while stack:
                node = stack.pop()
                component.append(node)
                for parent in reverse[node]:
                    if parent not in seen:
                        seen.add(parent)
                        stack.append(parent)
            if len(component) > 1 or start in graph[start]:
                result.append(sorted(component))
        return sorted(result)
