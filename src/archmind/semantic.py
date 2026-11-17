"""clang-uml schema-v3 class JSON adapter with conservative provenance."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .cmake import AnalysisError
from .models import Edge, Evidence, Node, Observation


def _location(root: Path, item: dict, diagnostics: list[str]) -> tuple[str | None, int | None]:
    location = item.get("source_location") or {}
    raw = location.get("file")
    if not isinstance(raw, str) or not raw:
        return None, None
    path = Path(raw)
    resolved = (path if path.is_absolute() else root / path).resolve()
    if root not in resolved.parents or not resolved.is_file():
        diagnostics.append(f"clang-uml source location outside project or missing: {raw}")
        return None, None
    line = location.get("line")
    return resolved.relative_to(root).as_posix(), line if isinstance(
        line, int
    ) and line > 0 else None


def _evidence(kind: str, path: str | None, line: int | None, description: str) -> Evidence:
    return Evidence(kind, path, line, description, "verified" if path and line else "unresolved")


def _method_key(qualified_class: str, method: dict) -> str:
    parameters = ",".join(p.get("type", "?") for p in method.get("parameters", []))
    suffix = " const" if method.get("is_const") else ""
    return f"METHOD:{qualified_class}::{method.get('name', '?')}({parameters}){suffix}"


def normalize(root: Path, document: dict) -> Observation:
    """Normalize only identities and relationships grounded in clang-uml JSON."""
    root = root.resolve()
    if (
        document.get("diagram_type") != "class"
        or document.get("metadata", {}).get("schema_version") != 3
    ):
        raise AnalysisError("Unsupported clang-uml class JSON schema (expected version 3)")
    nodes: dict[str, Node] = {}
    edges: dict[tuple[str, str, str], Edge] = {}
    diagnostics: list[str] = []
    by_uml_id: dict[str, str] = {}
    by_qualified: dict[str, dict] = {}
    for element in document.get("elements", []):
        if element.get("type") not in ("class", "struct"):
            continue
        qualified = element.get("display_name")
        uml_id = element.get("id")
        if not isinstance(qualified, str) or not qualified or not isinstance(uml_id, str):
            diagnostics.append("Skipped clang-uml element without stable qualified name or ID")
            continue
        kind = "STRUCT" if element.get("is_struct") or element.get("type") == "struct" else "CLASS"
        key = f"{kind}:{qualified}"
        path, line = _location(root, element, diagnostics)
        nodes[key] = Node(
            key,
            kind,
            element.get("name", qualified),
            {
                "qualified_name": qualified,
                "file_path": path,
                "line": line,
                "is_abstract": bool(element.get("is_abstract")),
                "clang_uml_id": uml_id,
            },
        )
        by_uml_id[uml_id] = key
        by_qualified[qualified] = element
        namespace = element.get("namespace") or ""
        if namespace:
            parent = None
            parts = namespace.split("::")
            for index in range(len(parts)):
                current = "::".join(parts[: index + 1])
                ns_key = f"NAMESPACE:{current}"
                nodes.setdefault(
                    ns_key,
                    Node(
                        ns_key,
                        "NAMESPACE",
                        parts[index],
                        {
                            "qualified_name": current,
                            "source_location_status": "derived_from_class_namespace",
                        },
                    ),
                )
                if parent:
                    edges[(parent, ns_key, "CONTAINS")] = Edge(
                        parent,
                        ns_key,
                        "CONTAINS",
                        "derived",
                        (
                            Evidence(
                                "clang_uml_namespace",
                                None,
                                None,
                                "Namespace hierarchy derived from class qualified name",
                                "derived",
                            ),
                        ),
                    )
                parent = ns_key
            edges[(parent, key, "CONTAINS")] = Edge(
                parent,
                key,
                "CONTAINS",
                "semantic",
                (
                    _evidence(
                        "clang_uml_declaration", path, line, "Class namespace and declaration"
                    ),
                ),
            )
        if path:
            file_key = f"FILE:{path}"
            nodes.setdefault(file_key, Node(file_key, "FILE", path))
            edges[(file_key, key, "CONTAINS")] = Edge(
                file_key,
                key,
                "CONTAINS",
                "semantic",
                (_evidence("clang_uml_declaration", path, line, "Class declared in source file"),),
            )
        for method in element.get("methods", []):
            method_key = _method_key(qualified, method)
            method_path, method_line = _location(root, method, diagnostics)
            nodes[method_key] = Node(
                method_key,
                "METHOD",
                method.get("name", "?"),
                {
                    "qualified_name": method_key.removeprefix("METHOD:"),
                    "file_path": method_path,
                    "line": method_line,
                    "return_type": method.get("type"),
                    "access": method.get("access"),
                    "is_virtual": bool(method.get("is_virtual")),
                },
            )
            edges[(key, method_key, "CONTAINS")] = Edge(
                key,
                method_key,
                "CONTAINS",
                "semantic",
                (
                    _evidence(
                        "clang_uml_method",
                        method_path,
                        method_line,
                        "Method declaration reported by clang-uml",
                    ),
                ),
            )
    for relationship in document.get("relationships", []):
        source = by_uml_id.get(str(relationship.get("source")))
        target = by_uml_id.get(str(relationship.get("destination")))
        if not source or not target:
            diagnostics.append("Skipped clang-uml relationship with an unresolved endpoint")
            continue
        relation = relationship.get("type")
        if relation == "extension":
            kind = "INHERITS"
        elif relation in ("association", "aggregation", "composition", "dependency"):
            kind = "USES_TYPE"
        else:
            diagnostics.append(f"Unsupported clang-uml relationship type: {relation}")
            continue
        label = relationship.get("label")
        source_element = by_qualified[nodes[source].metadata["qualified_name"]]
        matches = (
            [m for m in source_element.get("members", []) if m.get("name") == label]
            if label
            else []
        )
        if len(matches) == 1:
            path, line = _location(root, matches[0], diagnostics)
            evidence = _evidence(
                "clang_uml_member_type",
                path,
                line,
                f"Member {label} references {nodes[target].metadata['qualified_name']}",
            )
        else:
            # clang-uml relationships have no exact source location. A class
            # declaration line is not necessarily the relationship line.
            evidence = Evidence(
                "clang_uml_relationship",
                None,
                None,
                f"{relation} reported by clang-uml; exact relationship line unavailable",
                "derived",
            )
        edges[(source, target, kind)] = Edge(
            source,
            target,
            kind,
            "semantic",
            (evidence,),
            {"clang_uml_type": relation, "label": label, "access": relationship.get("access")},
        )
        source_namespace = source_element.get("namespace")
        target_element = by_qualified[nodes[target].metadata["qualified_name"]]
        target_namespace = target_element.get("namespace")
        if source_namespace and target_namespace and source_namespace != target_namespace:
            namespace_source = f"NAMESPACE:{source_namespace}"
            namespace_target = f"NAMESPACE:{target_namespace}"
            pair = (namespace_source, namespace_target, "DEPENDS_ON")
            support = Evidence(
                "clang_uml_namespace_dependency",
                evidence.file_path,
                evidence.line_start,
                f"Derived from {nodes[source].metadata['qualified_name']} {kind} "
                f"{nodes[target].metadata['qualified_name']}",
                "derived",
            )
            previous = edges.get(pair)
            evidence_items = previous.evidence if previous else ()
            edges[pair] = Edge(
                namespace_source,
                namespace_target,
                "DEPENDS_ON",
                "derived",
                evidence_items + (support,),
            )
    diagnostics.append("Free functions and call graphs are not emitted by clang-uml class diagrams")
    return Observation(tuple(nodes.values()), tuple(edges.values()), tuple(diagnostics))


def run(root: Path, build: Path) -> tuple[Observation, dict]:
    """Generate JSON from an existing compile database; never invoke a shell."""
    compilation_database = build / "compile_commands.json"
    if not compilation_database.is_file():
        raise AnalysisError(
            "clang-uml analysis requires compile_commands.json; use a Ninja/Makefiles analysis build"
        )
    executable = os.getenv("ARCHMIND_CLANG_UML") or shutil.which("clang-uml")
    if not executable:
        raise AnalysisError(
            "clang-uml executable not found; set ARCHMIND_CLANG_UML or install clang-uml"
        )
    try:
        threads = int(os.getenv("ARCHMIND_SEMANTIC_THREADS", "1"))
    except ValueError as exc:
        raise AnalysisError("ARCHMIND_SEMANTIC_THREADS must be an integer") from exc
    if not 1 <= threads <= 32:
        raise AnalysisError("ARCHMIND_SEMANTIC_THREADS must be between 1 and 32")
    with tempfile.TemporaryDirectory(prefix="archmind-semantic-") as temporary:
        output = Path(temporary) / "output"
        config = Path(temporary) / "config.yml"
        glob = [str(root / pattern) for pattern in ("**/*.cpp", "**/*.cc", "**/*.cxx")]
        config.write_text(
            f"relative_to: {json.dumps(str(root))}\n"
            f"compilation_database_dir: {json.dumps(str(build))}\n"
            f"output_directory: {json.dumps(str(output))}\n"
            "diagrams:\n  architecture:\n    type: class\n    glob:\n"
            + "".join(f"      - {json.dumps(pattern)}\n" for pattern in glob),
            encoding="utf-8",
        )
        try:
            process = subprocess.run(
                [str(executable), "-c", str(config), "-g", "json", "-t", str(threads), "-q"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
                timeout=300,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AnalysisError(f"clang-uml invocation failed: {exc}") from exc
        if process.returncode:
            raise AnalysisError(f"clang-uml failed: {process.stderr[-2000:]}")
        result = output / "architecture.json"
        if not result.is_file():
            raise AnalysisError("clang-uml did not produce architecture.json")
        try:
            document = json.loads(result.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise AnalysisError("clang-uml produced malformed JSON") from exc
    observation = normalize(root, document)
    metadata = {
        "clang_uml_version": document.get("metadata", {}).get("clang_uml_version"),
        "clang_uml_schema_version": document.get("metadata", {}).get("schema_version"),
        "llvm_version": document.get("metadata", {}).get("llvm_version"),
        "compile_commands_sha256": hashlib.sha256(compilation_database.read_bytes()).hexdigest(),
        "semantic_threads": threads,
    }
    return observation, metadata


def merge(base: Observation, semantic: Observation) -> Observation:
    nodes = {node.key: node for node in base.nodes}
    for node in semantic.nodes:
        nodes.setdefault(node.key, node)
    edges = {(edge.source, edge.target, edge.kind): edge for edge in base.edges}
    for edge in semantic.edges:
        edges.setdefault((edge.source, edge.target, edge.kind), edge)
    owned_files = {edge.target for edge in base.edges if edge.kind == "OWNS_FILE"}
    unowned = sum(
        1
        for node in semantic.nodes
        if node.kind in ("CLASS", "STRUCT")
        and node.metadata.get("file_path")
        and f"FILE:{node.metadata['file_path']}" not in owned_files
    )
    diagnostics = base.diagnostics + semantic.diagnostics
    if unowned:
        diagnostics += (
            f"{unowned} C++ classes have no CMake source ownership; target-level symbol tracing may be incomplete",
        )
    return Observation(tuple(nodes.values()), tuple(edges.values()), diagnostics)
