"""Conservative CMake File API codemodel-v2 adapter."""

import json
import posixpath
import re
import subprocess
from pathlib import Path

from .models import Edge, Evidence, Node, Observation


class AnalysisError(ValueError):
    pass


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AnalysisError(f"Invalid CMake File API response: {path.name}: {exc}") from exc


def _backtrace(target: dict, index: int | None) -> tuple[str | None, int | None, str | None]:
    graph = target.get("backtraceGraph", {})
    try:
        entry = graph["nodes"][index]
        file = graph["files"][entry["file"]]
        command = graph["commands"][entry["command"]] if "command" in entry else None
        return file.replace("\\", "/"), entry.get("line"), command
    except (KeyError, IndexError, TypeError):
        return None, None, None


def _local_link_backtrace(
    target: dict, index: int | None, own_dir: str
) -> tuple[str, int | None, str] | None:
    """Accept a link command only when its call stack starts in this target's CMakeLists."""
    file, line, command = _backtrace(target, index)
    if file is None or command is None or command.lower() != "target_link_libraries":
        return None
    graph = target.get("backtraceGraph", {})
    try:
        nodes = graph["nodes"]
        expected = posixpath.normpath(posixpath.join(own_dir, "CMakeLists.txt"))
        current = index
        seen = set()
        root_file = None
        callsite_line = None
        while current is not None:
            if current in seen:
                return None
            seen.add(current)
            entry = nodes[current]
            root_file = graph["files"][entry["file"]].replace("\\", "/")
            if root_file == expected and entry.get("line") is not None:
                callsite_line = entry["line"]
            current = entry.get("parent")
        if root_file != expected:
            return None
        description = (
            "Direct linker fragment with target_link_libraries backtrace; visibility unknown"
        )
        if callsite_line is not None and expected != file:
            description += f"; invoked from {expected}:{callsite_line}"
        return file, line, description
    except (KeyError, IndexError, TypeError):
        return None


def _artifact_for_fragment(path: str, artifact_to_id: dict[str, str]) -> str | None:
    """Resolve exact artifacts or ELF versioned names of their .so symlinks."""
    direct = artifact_to_id.get(path)
    if direct is not None:
        return direct
    versioned = re.fullmatch(r"(.+\.so)\.\d+(?:\.\d+)*", path)
    return artifact_to_id.get(versioned.group(1)) if versioned else None


def extract(
    root: Path,
    build: Path,
    config: str,
    configure: bool = False,
    export_compile_commands: bool = False,
    generator: str | None = None,
) -> tuple[Observation, dict]:
    root, build = root.resolve(), build.resolve()
    query = build / ".cmake/api/v1/query/codemodel-v2"
    if configure:
        query.parent.mkdir(parents=True, exist_ok=True)
        query.touch()
        args = ["cmake", "-S", str(root), "-B", str(build)]
        if generator:
            args.extend(["-G", generator])
        if export_compile_commands:
            args.append("-DCMAKE_EXPORT_COMPILE_COMMANDS=ON")
        proc = subprocess.run(
            args,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode:
            raise AnalysisError(f"CMake configuration failed: {proc.stderr[-2000:]}")
    reply = build / ".cmake/api/v1/reply"
    indexes = sorted(reply.glob("index-*.json"), reverse=True)
    if not indexes:
        raise AnalysisError(
            "No CMake File API index; configure the build with a codemodel-v2 query"
        )
    index = _load(indexes[0])
    try:
        model_file = index["reply"]["codemodel-v2"]["jsonFile"]
    except KeyError as exc:
        raise AnalysisError("Latest File API index has no codemodel-v2 reply") from exc
    model = _load(reply / model_file)
    configs = model.get("configurations", [])
    matches = [c for c in configs if c.get("name", "") == config]
    if not matches and len(configs) == 1 and configs[0].get("name", "") == "":
        matches = configs  # Single-config generator without CMAKE_BUILD_TYPE.
    if len(matches) != 1:
        raise AnalysisError(
            f"Configuration {config!r} not uniquely available: {[c.get('name') for c in configs]}"
        )
    selected = matches[0]
    targets = {t["id"]: (t, _load(reply / t["jsonFile"])) for t in selected.get("targets", [])}
    nodes = {"PROJECT:root": Node("PROJECT:root", "PROJECT", root.name)}
    edges = {}
    diagnostics = []
    by_id = {}
    artifact_to_id = {}
    for cmake_id, (summary, detail) in targets.items():
        name = summary["name"]
        directory = detail.get("paths", {}).get("source", ".").replace("\\", "/")
        key = f"CMAKE_TARGET:{name}:{directory}"
        by_id[cmake_id] = key
        for artifact in detail.get("artifacts", []):
            artifact_to_id[artifact["path"].replace("\\", "/")] = cmake_id
        nodes[key] = Node(
            key,
            "CMAKE_TARGET",
            name,
            {"cmake_id": cmake_id, "type": detail.get("type"), "directory": directory},
        )
        edges[("PROJECT:root", key, "CONTAINS")] = Edge("PROJECT:root", key, "CONTAINS", "declared")
        for source in detail.get("sources", []):
            path = source["path"].replace("\\", "/")
            file_key = f"FILE:{path}"
            nodes.setdefault(
                file_key,
                Node(file_key, "FILE", path, {"generated": bool(source.get("isGenerated"))}),
            )
            file, line, _ = _backtrace(detail, source.get("backtrace"))
            ev = Evidence(
                "cmake_source", file, line, "Source listed by CMake codemodel", "verified"
            )
            edges[(key, file_key, "OWNS_FILE")] = Edge(
                key, file_key, "OWNS_FILE", "declared", (ev,)
            )
    for cmake_id, (_, detail) in targets.items():
        source_key = by_id[cmake_id]
        own_dir = detail.get("paths", {}).get("source", ".").replace("\\", "/").strip("/")
        dependency_ids = {dep.get("id") for dep in detail.get("dependencies", [])}
        for dep in detail.get("dependencies", []):
            target_key = by_id.get(dep.get("id"))
            if target_key is None:
                diagnostics.append(
                    f"Unresolved CMake dependency ID {dep.get('id')} for {detail.get('name')}"
                )
                continue
            file, line, command = _backtrace(detail, dep.get("backtrace"))
            ev = Evidence(
                "cmake_build_dependency",
                file,
                line,
                "CMake codemodel target dependency; link semantics not implied",
                "verified" if file else "unresolved",
            )
            edges[(source_key, target_key, "BUILD_DEPENDS_ON")] = Edge(
                source_key, target_key, "BUILD_DEPENDS_ON", "declared", (ev,)
            )
        # Link fragments are actual linker inputs. Their command backtrace can
        # identify a direct declaration; dependencies alone cannot.
        build_dir = detail.get("paths", {}).get("build", ".").replace("\\", "/")
        for fragment in detail.get("link", {}).get("commandFragments", []):
            if fragment.get("role") != "libraries":
                continue
            token = fragment.get("fragment", "").strip().strip('"')
            path = posixpath.normpath(posixpath.join(build_dir, token))
            dep_id = _artifact_for_fragment(path, artifact_to_id)
            if dep_id is None or dep_id == cmake_id or dep_id not in dependency_ids:
                diagnostics.append(f"Unresolved linker fragment {token!r} for {detail.get('name')}")
                continue
            link_backtrace = _local_link_backtrace(detail, fragment.get("backtrace"), own_dir)
            if link_backtrace is not None:
                file, line, description = link_backtrace
                link_ev = Evidence(
                    "cmake_link",
                    file,
                    line,
                    description,
                    "verified",
                )
                target_key = by_id[dep_id]
                edges[(source_key, target_key, "LINKS_TO")] = Edge(
                    source_key, target_key, "LINKS_TO", "declared", (link_ev,)
                )
    version = index.get("cmake", {}).get("version", {}).get("string")
    metadata = {
        "cmake_version": version,
        "generator": index.get("cmake", {}).get("generator", {}).get("name"),
        "configuration": selected.get("name", ""),
        "adapter_version": "0.1.0",
    }
    return Observation(tuple(nodes.values()), tuple(edges.values()), tuple(diagnostics)), metadata
