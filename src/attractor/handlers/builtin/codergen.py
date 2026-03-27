from __future__ import annotations

from contextlib import nullcontext
import json
from pathlib import Path
from typing import Optional

from attractor.dsl.models import Duration

from attractor.engine.outcome import Outcome, OutcomeStatus

from ..base import CodergenBackend, HandlerRuntime

RUNTIME_CONTEXT_CARRYOVER_KEY = "_attractor.runtime.context_carryover"
STATUS_ENVELOPE_RESPONSE_CONTRACT = "status_envelope"
STATUS_ENVELOPE_PROMPT_APPENDIX = "\n".join(
    [
        "Structured response contract:",
        '- Return ONLY a JSON object.',
        '- Required top-level key: "outcome" with one of "success", "fail", "partial_success", or "retry".',
        '- Optional top-level keys: "preferred_label", "suggested_next_ids", "context_updates", "notes", "failure_reason", and "retryable".',
        '- Use "preferred_label" for routing; do not use legacy aliases.',
        '- "suggested_next_ids" must be a list of strings.',
        '- "context_updates" must be a JSON object.',
        '- Do not emit any other top-level keys.',
        '- Put machine-readable details in "context_updates", not ad hoc top-level fields.',
        '- If no routing or context updates are needed, prefer: {"outcome":"success"}',
    ]
)


class CodergenHandler:
    def __init__(self, backend: Optional[CodergenBackend] = None):
        self.backend = backend

    def execute(self, runtime: HandlerRuntime) -> Outcome:
        prompt = runtime.prompt.strip()
        if not prompt:
            label_attr = runtime.node_attrs.get("label")
            if label_attr:
                prompt = str(label_attr.value).strip()
            if not prompt:
                prompt = runtime.node_id
        prompt = _expand_goal(prompt, runtime.context, runtime.graph)
        prompt = _apply_response_contract(prompt, runtime.node_attrs)
        prompt = _apply_runtime_carryover(prompt, runtime.context)
        stage_dir = _ensure_stage_dir(runtime.logs_root, runtime.node_id)
        _write_stage_file(stage_dir, "prompt.md", prompt)

        if self.backend is None:
            response_text = f"[Simulated] Response for stage: {runtime.node_id}"
            outcome = _with_builtin_response_context(
                Outcome(
                    status=OutcomeStatus.SUCCESS,
                    notes=f"Stage completed: {runtime.node_id}",
                ),
                node_id=runtime.node_id,
                response_text=response_text,
            )
            _write_stage_file(stage_dir, "response.md", response_text)
            _write_status_file(stage_dir, outcome)
            return outcome

        timeout = _to_seconds(runtime.node_attrs.get("timeout"))
        with _backend_stage_logging_context(self.backend, runtime.node_id, runtime.logs_root):
            result = self.backend.run(runtime.node_id, prompt, runtime.context, timeout=timeout)
        outcome: Outcome
        response_text: str
        if isinstance(result, Outcome):
            outcome = _with_builtin_response_context(
                result,
                node_id=runtime.node_id,
                response_text=result.notes or result.failure_reason or "",
            )
            response_text = outcome.notes or outcome.failure_reason or ""
        elif isinstance(result, str):
            response_text = result
            outcome = _with_builtin_response_context(
                Outcome(status=OutcomeStatus.SUCCESS, notes=response_text),
                node_id=runtime.node_id,
                response_text=response_text,
            )
        elif result:
            outcome = _with_builtin_response_context(
                Outcome(status=OutcomeStatus.SUCCESS, notes="codergen backend success"),
                node_id=runtime.node_id,
                response_text="codergen backend success",
            )
            response_text = outcome.notes
        else:
            outcome = _with_builtin_response_context(
                Outcome(status=OutcomeStatus.FAIL, failure_reason="codergen backend failure"),
                node_id=runtime.node_id,
                response_text="codergen backend failure",
            )
            response_text = outcome.failure_reason
        _write_stage_file(stage_dir, "response.md", response_text)
        _write_status_file(stage_dir, outcome)
        return outcome


def _expand_goal(prompt: str, context, graph) -> str:
    goal = context.get("graph.goal")
    if goal in (None, ""):
        goal_attr = graph.graph_attrs.get("goal")
        if goal_attr is not None:
            goal = goal_attr.value
    if goal is None:
        goal = ""
    return prompt.replace("$goal", str(goal))


def _apply_runtime_carryover(prompt: str, context) -> str:
    carryover = str(context.get(RUNTIME_CONTEXT_CARRYOVER_KEY, "") or "").strip()
    if not carryover:
        return prompt
    return "\n\n".join(
        [
            "Context carryover:",
            carryover,
            "Current stage task:",
            prompt,
        ]
    )


def _backend_stage_logging_context(backend: object, node_id: str, logs_root: Path | None):
    binder = getattr(backend, "bind_stage_raw_rpc_log", None)
    if callable(binder):
        return binder(node_id, logs_root)
    return nullcontext()


def _apply_response_contract(prompt: str, node_attrs) -> str:
    attr = node_attrs.get("codergen.response_contract")
    if attr is None:
        return prompt
    contract_name = str(attr.value).strip().lower().replace("-", "_")
    if contract_name != STATUS_ENVELOPE_RESPONSE_CONTRACT:
        return prompt
    return "\n\n".join([prompt, STATUS_ENVELOPE_PROMPT_APPENDIX])


def _with_builtin_response_context(outcome: Outcome, *, node_id: str, response_text: str) -> Outcome:
    merged_updates = {
        "last_stage": node_id,
        "last_response": response_text[:200],
    }
    merged_updates.update(dict(outcome.context_updates))
    outcome.context_updates = merged_updates
    return outcome


def _to_seconds(attr) -> float | None:
    if not attr:
        return None
    value = attr.value
    if isinstance(value, Duration):
        unit = value.unit
        if unit == "ms":
            return value.value / 1000
        if unit == "s":
            return value.value
        if unit == "m":
            return value.value * 60
        if unit == "h":
            return value.value * 3600
        if unit == "d":
            return value.value * 86400
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _ensure_stage_dir(logs_root: Path | None, node_id: str) -> Path | None:
    if logs_root is None:
        return None
    stage_dir = logs_root / node_id
    stage_dir.mkdir(parents=True, exist_ok=True)
    return stage_dir


def _write_stage_file(stage_dir: Path | None, filename: str, content: str) -> None:
    if stage_dir is None:
        return
    (stage_dir / filename).write_text(content + "\n", encoding="utf-8")


def _write_status_file(stage_dir: Path | None, outcome: Outcome) -> None:
    if stage_dir is None:
        return
    payload = {
        "outcome": outcome.status.value,
        "preferred_label": outcome.preferred_label,
        "suggested_next_ids": list(outcome.suggested_next_ids),
        "context_updates": dict(outcome.context_updates),
        "notes": outcome.notes,
    }
    with (stage_dir / "status.json").open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
