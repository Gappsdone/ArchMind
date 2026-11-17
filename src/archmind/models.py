"""Normalized, validated CMake graph observations."""

from dataclasses import dataclass, field
from typing import Literal

NodeKind = Literal["PROJECT", "CMAKE_TARGET", "FILE", "EXTERNAL_LIBRARY"]
EdgeKind = Literal["CONTAINS", "OWNS_FILE", "LINKS_TO", "BUILD_DEPENDS_ON"]


@dataclass(frozen=True)
class Node:
    key: str
    kind: NodeKind
    name: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Evidence:
    kind: str
    file_path: str | None
    line_start: int | None
    description: str
    confidence: Literal["verified", "derived", "unresolved"]


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    kind: EdgeKind
    origin: Literal["declared", "semantic", "derived"]
    evidence: tuple[Evidence, ...] = ()
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Observation:
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    diagnostics: tuple[str, ...] = ()
