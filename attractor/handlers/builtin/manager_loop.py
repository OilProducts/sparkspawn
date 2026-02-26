from __future__ import annotations

import re
import time

from attractor.dsl.models import DotAttribute, Duration
from attractor.engine.outcome import Outcome, OutcomeStatus

from ..base import HandlerRuntime


class ManagerLoopHandler:
    def execute(self, runtime: HandlerRuntime) -> Outcome:
        poll_interval = _poll_interval_seconds(runtime.node_attrs.get("manager.poll_interval"))
        max_cycles = _max_cycles(runtime.node_attrs.get("manager.max_cycles"))
        for _ in range(max_cycles):
            if poll_interval > 0:
                time.sleep(poll_interval)
        return Outcome(
            status=OutcomeStatus.FAIL,
            failure_reason="Max cycles exceeded",
        )


def _poll_interval_seconds(attr: DotAttribute | None) -> float:
    if attr is None:
        return 45.0

    value = attr.value
    if isinstance(value, Duration):
        return _seconds_from_duration(value.value, value.unit)
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return _parse_duration_string(str(value), 45.0)


def _max_cycles(attr: DotAttribute | None) -> int:
    if attr is None:
        return 1000

    value = attr.value
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value))
    try:
        return max(0, int(str(value).strip()))
    except ValueError:
        return 1000


def _parse_duration_string(raw: str, default: float) -> float:
    value = raw.strip().lower()
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        match = re.fullmatch(r"(?P<num>\d+)(?P<unit>ms|s|m|h|d)", value)
        if not match:
            return default
        return _seconds_from_duration(int(match.group("num")), match.group("unit"))


def _seconds_from_duration(amount: int, unit: str) -> float:
    if unit == "ms":
        return amount / 1000
    if unit == "s":
        return float(amount)
    if unit == "m":
        return amount * 60.0
    if unit == "h":
        return amount * 3600.0
    if unit == "d":
        return amount * 86400.0
    return 45.0
