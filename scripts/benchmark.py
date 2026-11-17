"""Synthetic M1 query benchmark. Run with `uv run python scripts/benchmark.py`."""

import os
import random
import statistics
import tempfile
import time
from pathlib import Path

from archmind.core import Store
from archmind.models import Edge, Node, Observation

random.seed(42)
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    (root / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.20)\n")
    db = Store(root / "bench.db")
    project = db.project_add("Benchmark", root)
    sid = "synthetic-benchmark"
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO snapshots (id,project_id,cmake_config,build_directory,status,created_at) VALUES (?,?,?,?,'building',?)",
            (sid, project["id"], "", "", "now"),
        )
    nodes = tuple(Node(f"T{i:05d}", "CMAKE_TARGET", f"T{i:05d}") for i in range(10_000))
    pairs = {(i, i + 1) for i in range(9_999)}
    while len(pairs) < 50_000:
        i = random.randrange(9_999)
        j = random.randrange(i + 1, 10_000)
        pairs.add((i, j))
    edges = tuple(
        Edge(f"T{i:05d}", f"T{j:05d}", "BUILD_DEPENDS_ON", "declared") for i, j in sorted(pairs)
    )
    started = time.perf_counter()
    db._publish(sid, Observation(nodes, edges), {})
    import_seconds = time.perf_counter() - started
    ids = [db.node_by_key(sid, f"T{i:05d}")["id"] for i in random.sample(range(10_000), 100)]
    times = []
    for node_id in ids:
        start = time.perf_counter()
        db.edges(sid, source_id=node_id, kind="BUILD_DEPENDS_ON")
        times.append((time.perf_counter() - start) * 1000)
    start = time.perf_counter()
    cycles = db.cycles(sid)
    scc_seconds = time.perf_counter() - start
    start = time.perf_counter()
    overview = db.subgraph(sid, limit=200)
    overview_ms = (time.perf_counter() - start) * 1000
    start = time.perf_counter()
    neighborhood = db.subgraph(sid, center_id=ids[0], depth=2, limit=200)
    neighborhood_ms = (time.perf_counter() - start) * 1000
    peak = "unavailable"
    status = Path("/proc/self/status")
    if os.name == "posix" and status.is_file():
        peak = next(
            (
                line.split(":", 1)[1].strip()
                for line in status.read_text().splitlines()
                if line.startswith("VmHWM:")
            ),
            peak,
        )
    print(
        f"nodes=10000 edges=50000 import_s={import_seconds:.3f} direct_p95_ms={statistics.quantiles(times, n=20)[18]:.3f} scc_s={scc_seconds:.3f} cycles={len(cycles)} peak_rss={peak}"
    )
    print(
        f"overview_ms={overview_ms:.3f} overview_nodes={len(overview['nodes'])} "
        f"neighborhood_ms={neighborhood_ms:.3f} neighborhood_nodes={len(neighborhood['nodes'])}"
    )
