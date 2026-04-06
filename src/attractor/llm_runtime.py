from __future__ import annotations

from typing import Any, Dict, Optional, Protocol

from attractor.dsl.models import DotAttribute, DotNode


RUNTIME_LAUNCH_MODEL_KEY = "_attractor.runtime.launch_model"

_NON_LLM_BACKEND_SHAPES = {
    "Mdiamond",
    "Msquare",
    "hexagon",
    "diamond",
    "component",
    "parallelogram",
    "house",
}


class ContextLike(Protocol):
    def get(self, key: str, default: Any = None) -> Any:
        ...


def _normalize_optional_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def resolve_effective_llm_model(
    node_attrs: Dict[str, DotAttribute],
    context: ContextLike,
    *,
    fallback_model: Optional[str] = None,
) -> Optional[str]:
    node_model = _normalize_optional_text(getattr(node_attrs.get("llm_model"), "value", None))
    if node_model:
        return node_model

    runtime_launch_model = _normalize_optional_text(context.get(RUNTIME_LAUNCH_MODEL_KEY, ""))
    if runtime_launch_model:
        return runtime_launch_model

    normalized_fallback = _normalize_optional_text(fallback_model)
    if normalized_fallback:
        return normalized_fallback
    return None


def resolved_llm_backend_handler_type(node: DotNode) -> str:
    explicit = _normalize_optional_text(getattr(node.attrs.get("type"), "value", None))
    if explicit:
        return explicit

    shape = _normalize_optional_text(getattr(node.attrs.get("shape"), "value", None))
    if shape == "tripleoctagon":
        return "parallel.fan_in"
    if shape in _NON_LLM_BACKEND_SHAPES:
        return ""
    return "codergen"


def node_uses_llm_backend(node: DotNode) -> bool:
    return resolved_llm_backend_handler_type(node) in {"codergen", "parallel.fan_in"}
