"""Internal DAG representation and cycle detection."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .exceptions import CycleDetectedError


@dataclass(slots=True)
class Node:
    name: str
    upstream: set[str] = field(default_factory=set)
    downstream: set[str] = field(default_factory=set)


class DAG:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}

    def add_node(self, name: str) -> None:
        if name not in self.nodes:
            self.nodes[name] = Node(name=name)

    def add_edge(self, upstream: str, downstream: str) -> None:
        self.add_node(upstream)
        self.add_node(downstream)
        self.nodes[upstream].downstream.add(downstream)
        self.nodes[downstream].upstream.add(upstream)

    def topological_sort(self) -> list[str]:
        # Kahn's algorithm with deterministic ordering
        in_degree = {n: len(node.upstream) for n, node in self.nodes.items()}
        ready = sorted([n for n, d in in_degree.items() if d == 0])
        order: list[str] = []
        while ready:
            # pop the smallest name for stable results
            current = ready.pop(0)
            order.append(current)
            for child in sorted(self.nodes[current].downstream):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    # keep ready sorted
                    from bisect import insort

                    insort(ready, child)
        if len(order) != len(self.nodes):
            # Return nodes that still have in-degree > 0 deterministically
            remaining = sorted([n for n, d in in_degree.items() if d > 0])
            raise CycleDetectedError(remaining)
        return order

    def subgraph(self, names: Iterable[str]) -> DAG:
        sg = DAG()
        for name in names:
            if name not in self.nodes:
                continue
            sg.add_node(name)
            for d in self.nodes[name].downstream:
                if d in names:
                    sg.add_edge(name, d)
        return sg

    # Export utilities
    def to_dot(self) -> str:
        lines = ["digraph G {"]
        for name, node in self.nodes.items():
            if not node.downstream:
                lines.append(f'  "{name}";')
            for d in node.downstream:
                lines.append(f'  "{name}" -> "{d}";')
        lines.append("}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            name: {"upstream": sorted(n.upstream), "downstream": sorted(n.downstream)}
            for name, n in self.nodes.items()
        }
