from __future__ import annotations

import copy
from dataclasses import dataclass

from attractor.dsl.models import DotAttribute, DotGraph, DotNode


@dataclass(frozen=True)
class GraphMergeTransform:
    module_graphs: tuple[DotGraph, ...]

    def __init__(self, *module_graphs: DotGraph):
        if not module_graphs:
            raise ValueError("GraphMergeTransform requires at least one module graph")
        object.__setattr__(self, "module_graphs", tuple(module_graphs))

    def apply(self, graph: DotGraph) -> DotGraph:
        for module in self.module_graphs:
            self._merge_graph_attrs(graph, module)
            self._merge_nodes(graph, module)
            self._merge_edges(graph, module)
        return graph

    def _merge_graph_attrs(self, target: DotGraph, module: DotGraph) -> None:
        for key, attr in module.graph_attrs.items():
            if key in target.graph_attrs:
                continue
            target.graph_attrs[key] = copy.deepcopy(attr)

    def _merge_nodes(self, target: DotGraph, module: DotGraph) -> None:
        for node_id, incoming_node in module.nodes.items():
            existing_node = target.nodes.get(node_id)
            if existing_node is None:
                target.nodes[node_id] = copy.deepcopy(incoming_node)
                continue
            self._merge_existing_node(existing_node, incoming_node)

    def _merge_existing_node(self, existing_node: DotNode, incoming_node: DotNode) -> None:
        for key, incoming_attr in incoming_node.attrs.items():
            existing_attr = existing_node.attrs.get(key)
            if existing_attr is None:
                existing_node.attrs[key] = copy.deepcopy(incoming_attr)
                continue
            if not _attrs_equal(existing_attr, incoming_attr):
                raise ValueError(
                    f"cannot merge node '{existing_node.node_id}': conflicting attribute '{key}'"
                )
        existing_node.explicit_attr_keys.update(incoming_node.explicit_attr_keys)

    def _merge_edges(self, target: DotGraph, module: DotGraph) -> None:
        for edge in module.edges:
            target.edges.append(copy.deepcopy(edge))


def _attrs_equal(left: DotAttribute, right: DotAttribute) -> bool:
    return left.value_type == right.value_type and left.value == right.value
