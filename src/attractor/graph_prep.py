from __future__ import annotations

from typing import Iterable, List, Mapping

from attractor.dsl import Diagnostic, parse_dot, validate_graph
from attractor.dsl.formatter import format_dot
from attractor.dsl.models import DotAttribute, DotGraph


DEFAULT_MAX_RETRIES_KEY = "default_max_retries"
LEGACY_DEFAULT_MAX_RETRY_KEY = "default_max_retry"


def normalize_graph_attr_aliases(graph: DotGraph) -> DotGraph:
    legacy_attr = graph.graph_attrs.pop(LEGACY_DEFAULT_MAX_RETRY_KEY, None)
    canonical_attr = graph.graph_attrs.get(DEFAULT_MAX_RETRIES_KEY)
    if canonical_attr is None and legacy_attr is not None:
        graph.graph_attrs[DEFAULT_MAX_RETRIES_KEY] = DotAttribute(
            key=DEFAULT_MAX_RETRIES_KEY,
            value=legacy_attr.value,
            value_type=legacy_attr.value_type,
            line=legacy_attr.line,
        )
    return graph


def canonicalize_graph_source(source: str) -> str:
    graph = normalize_graph_attr_aliases(parse_dot(source))
    return format_dot(graph)


def build_transform_pipeline(extra_transforms: Iterable[object] = ()) -> object:
    # Lazy import avoids transform package initialization during module import.
    from attractor.transforms import GoalVariableTransform, ModelStylesheetTransform, TransformPipeline

    pipeline = TransformPipeline()
    pipeline.register(GoalVariableTransform())
    pipeline.register(ModelStylesheetTransform())
    for transform in extra_transforms:
        pipeline.register(transform)
    return pipeline


def apply_graph_transforms(graph: DotGraph, extra_transforms: Iterable[object] = ()) -> DotGraph:
    normalize_graph_attr_aliases(graph)
    return build_transform_pipeline(extra_transforms).apply(graph)


def prepare_graph(graph: DotGraph, extra_transforms: Iterable[object] = ()) -> tuple[DotGraph, List[Diagnostic]]:
    transformed = apply_graph_transforms(graph, extra_transforms)
    diagnostics = validate_graph(transformed)
    return transformed, diagnostics


def parse_prepare_graph(source: str, extra_transforms: Iterable[object] = ()) -> tuple[DotGraph, List[Diagnostic]]:
    graph = parse_dot(source)
    return prepare_graph(graph, extra_transforms)


def resolve_default_max_retries_attr(attrs: Mapping[str, DotAttribute]) -> DotAttribute | None:
    canonical = attrs.get(DEFAULT_MAX_RETRIES_KEY)
    if canonical is not None:
        return canonical
    return attrs.get(LEGACY_DEFAULT_MAX_RETRY_KEY)


def resolve_default_max_retries_value(attrs: Mapping[str, DotAttribute], default: int = 0) -> int:
    attr = resolve_default_max_retries_attr(attrs)
    if attr is None:
        return default
    value = attr.value
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default
