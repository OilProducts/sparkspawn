from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from typing import Any

logger = logging.getLogger(__name__)


def _validate_string(value: Any, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")


def _validate_boolean(value: Any, field_name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a boolean")


def _validate_integer_or_none(value: Any, field_name: str) -> None:
    if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
        raise TypeError(f"{field_name} must be an integer or None")


def _normalize_optional_cost(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a number or None")
    return float(value)


def _normalize_aliases(value: Any) -> list[str]:
    if isinstance(value, str):
        raise TypeError("aliases must be an iterable of strings")
    try:
        aliases = list(value)
    except TypeError as error:
        raise TypeError("aliases must be an iterable of strings") from error

    for alias in aliases:
        if not isinstance(alias, str):
            raise TypeError("aliases must contain strings")
    return aliases


@dataclass(slots=True)
class ModelInfo:
    id: str
    provider: str
    display_name: str
    context_window: int
    supports_tools: bool
    supports_vision: bool
    supports_reasoning: bool
    max_output: int | None = None
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    aliases: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _validate_string(self.id, "id")
        _validate_string(self.provider, "provider")
        _validate_string(self.display_name, "display_name")
        _validate_integer_or_none(self.context_window, "context_window")
        _validate_boolean(self.supports_tools, "supports_tools")
        _validate_boolean(self.supports_vision, "supports_vision")
        _validate_boolean(self.supports_reasoning, "supports_reasoning")
        _validate_integer_or_none(self.max_output, "max_output")

        self.input_cost_per_million = _normalize_optional_cost(
            self.input_cost_per_million,
            "input_cost_per_million",
        )
        self.output_cost_per_million = _normalize_optional_cost(
            self.output_cost_per_million,
            "output_cost_per_million",
        )
        self.aliases = _normalize_aliases(self.aliases)


def _catalog_resource() -> resources.abc.Traversable:
    return resources.files(__package__).joinpath("data/models.json")


@lru_cache(maxsize=1)
def _load_catalog() -> tuple[ModelInfo, ...]:
    catalog_path = _catalog_resource()
    logger.debug("Loading model catalog from %s", catalog_path)
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("model catalog must be a JSON array")

    catalog: list[ModelInfo] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise TypeError("model catalog entries must be objects")
        catalog.append(ModelInfo(**entry))
    return tuple(catalog)


def get_model_info(model_id: str) -> ModelInfo | None:
    if not isinstance(model_id, str):
        raise TypeError("model_id must be a string")

    logger.debug("Looking up model info for %s", model_id)
    normalized_model_id = model_id.casefold()
    for model in _load_catalog():
        if model.id.casefold() == normalized_model_id:
            return model
        if any(alias.casefold() == normalized_model_id for alias in model.aliases):
            return model
    return None


def list_models(provider: str | None = None) -> list[ModelInfo]:
    if provider is not None and not isinstance(provider, str):
        raise TypeError("provider must be a string or None")

    logger.debug("Listing models for provider=%s", provider)
    catalog = _load_catalog()
    if provider is None:
        return list(catalog)

    normalized_provider = provider.casefold()
    return [
        model
        for model in catalog
        if model.provider.casefold() == normalized_provider
    ]


def _supports_capability(model: ModelInfo, capability: str | None) -> bool:
    if capability is None:
        return True
    if not isinstance(capability, str):
        raise TypeError("capability must be a string or None")

    capability_key = capability.casefold().removeprefix("supports_")
    capability_field = {
        "tools": "supports_tools",
        "vision": "supports_vision",
        "reasoning": "supports_reasoning",
    }.get(capability_key)
    if capability_field is None:
        return False
    return getattr(model, capability_field)


def get_latest_model(provider: str, capability: str | None = None) -> ModelInfo | None:
    if not isinstance(provider, str):
        raise TypeError("provider must be a string")

    logger.debug(
        "Selecting latest model for provider=%s capability=%s",
        provider,
        capability,
    )
    for model in list_models(provider):
        if not _supports_capability(model, capability):
            continue
        logger.debug(
            "Selected latest model for provider=%s capability=%s: %s",
            provider,
            capability,
            model.id,
        )
        return model

    logger.debug(
        "No catalog model matched provider=%s capability=%s",
        provider,
        capability,
    )
    return None


__all__ = ["ModelInfo", "get_model_info", "get_latest_model", "list_models"]
