from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, List, Tuple

from attractor.dsl.models import DotAttribute, DotGraph, DotNode, DotValueType


_SELECTOR_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)

_ALLOWED_PROPERTIES = {"llm_model", "llm_provider", "reasoning_effort"}


@dataclass
class _StyleRule:
    selector: str
    properties: Dict[str, str]
    order: int


class ModelStylesheetTransform:
    def apply(self, graph: DotGraph) -> DotGraph:
        style_attr = graph.graph_attrs.get("model_stylesheet")
        rules: List[_StyleRule] = []
        stylesheet_line = 0
        if style_attr and isinstance(style_attr.value, str) and style_attr.value.strip() != "":
            rules = _parse_rules(style_attr.value)
            stylesheet_line = style_attr.line

        graph_defaults = _graph_default_model_attrs(graph)
        for node in graph.nodes.values():
            self._apply_rules(node, rules, stylesheet_line, graph_defaults)

        return graph

    def _apply_rules(
        self,
        node: DotNode,
        rules: List[_StyleRule],
        line: int,
        graph_defaults: Dict[str, Tuple[str, int]],
    ) -> None:
        candidates: Dict[str, Tuple[int, int, str]] = {}
        for rule in rules:
            if not _selector_matches(rule.selector, node):
                continue
            specificity = _selector_specificity(rule.selector)
            for prop, value in rule.properties.items():
                current = candidates.get(prop)
                entry = (specificity, rule.order, value)
                if current is None or entry > current:
                    candidates[prop] = entry

        for prop in _ALLOWED_PROPERTIES:
            existing = node.attrs.get(prop)
            # Preserve explicit per-node attributes from source; allow stylesheet
            # to replace parser/default-injected placeholders and inherited node defaults.
            if existing is not None and _is_explicit_node_attr(existing, node):
                continue
            if prop in candidates:
                value = candidates[prop][2]
                value_line = line
            elif prop in graph_defaults:
                value, value_line = graph_defaults[prop]
            else:
                continue
            node.attrs[prop] = DotAttribute(
                key=prop,
                value=value,
                value_type=DotValueType.STRING,
                line=value_line,
            )


def _parse_rules(stylesheet: str) -> List[_StyleRule]:
    rules: List[_StyleRule] = []
    for idx, match in enumerate(_SELECTOR_RE.finditer(stylesheet)):
        selector = match.group(1).strip()
        body = match.group(2).strip()
        properties: Dict[str, str] = {}
        for stmt in [s.strip() for s in body.split(";") if s.strip()]:
            if ":" not in stmt:
                continue
            raw_key, raw_value = stmt.split(":", 1)
            key = raw_key.strip()
            value = _strip_quotes(raw_value.strip())
            if key in _ALLOWED_PROPERTIES:
                properties[key] = value
        if selector and properties:
            rules.append(_StyleRule(selector=selector, properties=properties, order=idx))
    return rules


def _selector_matches(selector: str, node: DotNode) -> bool:
    selector = selector.strip()
    if selector == "*":
        return True

    if selector.startswith("#"):
        return node.node_id == selector[1:]

    if selector.startswith("."):
        class_attr = node.attrs.get("class")
        if not class_attr:
            return False
        classes = [c.strip() for c in str(class_attr.value).split(",") if c.strip()]
        return selector[1:] in classes

    return False


def _selector_specificity(selector: str) -> int:
    selector = selector.strip()
    if selector.startswith("#"):
        return 3
    if selector.startswith("."):
        return 2
    if selector == "*":
        return 0
    return -1


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def _graph_default_model_attrs(graph: DotGraph) -> Dict[str, Tuple[str, int]]:
    defaults: Dict[str, Tuple[str, int]] = {}
    for prop in _ALLOWED_PROPERTIES:
        attr = graph.graph_attrs.get(prop)
        if not attr or attr.line <= 0:
            continue
        value = str(attr.value).strip()
        if value == "":
            continue
        defaults[prop] = (value, attr.line)
    return defaults


def _is_explicit_node_attr(attr: DotAttribute, node: DotNode) -> bool:
    if attr.line <= 0:
        return False
    # Attributes inherited from `node [...]` defaults appear on an earlier line
    # than the node declaration itself; treat those as overridable defaults.
    if node.line > 0 and attr.line < node.line:
        return False
    return True
