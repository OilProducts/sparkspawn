from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Dict, List, Tuple

from attractor.engine.context import Context


@dataclass(frozen=True)
class RuntimePreambleTransform:
    node_outcomes_key: str = "_attractor.node_outcomes"

    def apply(
        self,
        fidelity: str,
        context: Context,
        completed_nodes: List[str],
    ) -> str:
        mode = fidelity.strip().lower()
        if mode == "full":
            return ""

        goal = str(context.get("graph.goal", "")).strip()
        run_id = str(context.get("internal.run_id", "")).strip()
        statuses = context.get(self.node_outcomes_key, {})
        if not isinstance(statuses, dict):
            statuses = {}

        if mode == "truncate":
            return "\n".join(
                [
                    "carryover:truncate",
                    f"goal={goal}",
                    f"run_id={run_id}",
                ]
            )

        context_items = self._carryover_context_items(context.snapshot())
        if mode == "compact":
            lines = [
                "carryover:compact",
                f"goal={goal}",
                f"run_id={run_id}",
            ]
            if completed_nodes:
                completed_summary = ", ".join(
                    f"{node_id}:{statuses.get(node_id, '')}" for node_id in completed_nodes
                )
                lines.append(f"completed={completed_summary}")
            for key, value in context_items[:8]:
                lines.append(f"- {key}={value}")
            return "\n".join(lines)

        summary_limits = {
            "summary:low": (3, 4),
            "summary:medium": (6, 8),
            "summary:high": (12, 16),
        }
        if mode in summary_limits:
            max_stages, max_context_items = summary_limits[mode]
            recent_nodes = completed_nodes[-max_stages:]
            recent_summary = ", ".join(
                f"{node_id}:{statuses.get(node_id, '')}" for node_id in recent_nodes
            )
            lines = [
                f"carryover:{mode}",
                f"goal={goal}",
                f"run_id={run_id}",
                f"recent_stages={recent_summary}",
                f"log_entries={len(context.logs)}",
            ]
            for key, value in context_items[:max_context_items]:
                lines.append(f"{key}={value}")
            return "\n".join(lines)

        return self.apply("compact", context, completed_nodes)

    def _carryover_context_items(self, snapshot: Dict[str, object]) -> List[Tuple[str, str]]:
        items: List[Tuple[str, str]] = []
        for key in sorted(snapshot.keys()):
            if key in {"graph.goal", "internal.run_id"}:
                continue
            if key.startswith("_attractor.") or key.startswith("internal."):
                continue
            items.append((key, _to_context_text(snapshot[key])))
        return items


def _to_context_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value)
    return json.dumps(value, sort_keys=True)
