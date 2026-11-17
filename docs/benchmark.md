# M1 synthetic benchmark (2026-11-17)

Machine: Linux x86-64, Python 3.12.15, 8 GiB system RAM, warm local filesystem. `uv run python scripts/benchmark.py` generated 10,000 targets and 50,000 directed acyclic build edges using seed 42. SQLite import took 2.263 s. One hundred random direct edge queries had p95 109.097 ms. Iterative SCC took 0.162 s and found zero cycles. Peak process RSS (`/proc/self/status` VmHWM) was 203,544 kB. CMake configuration and File API extraction are separate from this synthetic import measurement. These results do not establish 2M-LOC or Windows performance.
