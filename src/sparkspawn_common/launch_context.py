from __future__ import annotations

import copy
import math
from typing import Any


def normalize_launch_context(
    value: Any,
    *,
    source_name: str,
) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{source_name} launch_context must be an object.")
    normalized: dict[str, Any] = {}
    for key, entry in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{source_name} launch_context keys must be strings.")
        if not key.startswith("context."):
            raise ValueError(f"{source_name} launch_context key must use the context.* namespace: {key}")
        _validate_json_compatible_value(entry, path=key, source_name=source_name)
        normalized[key] = copy.deepcopy(entry)
    return normalized


def _validate_json_compatible_value(value: Any, *, path: str, source_name: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValueError(f"{source_name} launch_context value at {path} must be JSON-compatible.")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_compatible_value(item, path=f"{path}[{index}]", source_name=source_name)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{source_name} launch_context object keys must be strings at {path}.")
            _validate_json_compatible_value(item, path=f"{path}.{key}", source_name=source_name)
        return
    raise ValueError(f"{source_name} launch_context value at {path} must be JSON-compatible.")
