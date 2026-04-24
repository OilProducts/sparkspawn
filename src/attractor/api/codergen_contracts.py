from __future__ import annotations

from dataclasses import dataclass
import json

from attractor.engine.context_contracts import (
    ContextWriteContract,
    validate_context_updates_against_contract,
)
from attractor.engine.outcome import FailureKind, Outcome, OutcomeStatus
from attractor.engine.status_envelope_prompting import (
    build_status_envelope_context_updates_contract_text,
    format_status_envelope_allowed_keys,
)


_STRUCTURED_OUTCOME_KEYS = {
    "outcome",
    "preferred_label",
    "suggested_next_ids",
    "context_updates",
    "notes",
    "failure_reason",
    "retryable",
}


@dataclass(frozen=True)
class PlainTextParseResult:
    raw_text: str


@dataclass(frozen=True)
class ModeledOutcomeParseResult:
    outcome: Outcome


@dataclass(frozen=True)
class StructuredContractViolation:
    response_contract: str
    raw_text: str
    reason: str
    write_contract: ContextWriteContract | None = None


def validate_write_contract_violation(
    outcome: Outcome,
    *,
    write_contract: ContextWriteContract | None,
    response_contract: str,
    raw_text: str,
) -> StructuredContractViolation | None:
    if not has_response_contract(response_contract) or write_contract is None:
        return None
    violation = validate_context_updates_against_contract(outcome.context_updates, write_contract)
    if violation is None:
        return None
    return StructuredContractViolation(
        response_contract=response_contract,
        raw_text=raw_text.strip(),
        reason=violation.format_reason(),
        write_contract=write_contract,
    )


def with_write_contract(
    violation: StructuredContractViolation,
    write_contract: ContextWriteContract | None,
) -> StructuredContractViolation:
    if violation.write_contract is write_contract:
        return violation
    return StructuredContractViolation(
        response_contract=violation.response_contract,
        raw_text=violation.raw_text,
        reason=violation.reason,
        write_contract=write_contract,
    )


def coerce_structured_text_outcome(
    text: str,
    *,
    response_contract: str = "",
) -> PlainTextParseResult | ModeledOutcomeParseResult | StructuredContractViolation:
    raw_text = text.strip()
    candidate, envelope_error = extract_structured_outcome_payload(
        text,
        require_contract=has_response_contract(response_contract),
    )
    if envelope_error is not None:
        return _contract_violation_or_invalid_outcome(raw_text, envelope_error, response_contract)
    if candidate is None:
        return PlainTextParseResult(raw_text=raw_text)

    preferred_label = candidate.get("preferred_label", "")
    suggested_next_ids = candidate.get("suggested_next_ids", [])
    context_updates = candidate.get("context_updates", {})
    notes = candidate.get("notes", "")
    failure_reason = candidate.get("failure_reason", "")
    retryable = candidate.get("retryable", None)

    if not isinstance(preferred_label, str):
        return _contract_violation_or_invalid_outcome(
            text,
            "invalid structured status envelope: preferred_label must be a string",
            response_contract,
        )
    if not isinstance(suggested_next_ids, list) or any(not isinstance(item, str) for item in suggested_next_ids):
        return _contract_violation_or_invalid_outcome(
            text,
            "invalid structured status envelope: suggested_next_ids must be a list of strings",
            response_contract,
        )
    if not isinstance(context_updates, dict):
        return _contract_violation_or_invalid_outcome(
            text,
            "invalid structured status envelope: context_updates must be an object",
            response_contract,
        )
    if notes is not None and not isinstance(notes, str):
        return _contract_violation_or_invalid_outcome(
            text,
            "invalid structured status envelope: notes must be a string",
            response_contract,
        )
    if failure_reason is not None and not isinstance(failure_reason, str):
        return _contract_violation_or_invalid_outcome(
            text,
            "invalid structured status envelope: failure_reason must be a string",
            response_contract,
        )
    if retryable is not None and not isinstance(retryable, bool):
        return _contract_violation_or_invalid_outcome(
            text,
            "invalid structured status envelope: retryable must be a boolean",
            response_contract,
        )

    outcome_name = str(candidate.get("outcome", "")).strip().lower()
    try:
        status = OutcomeStatus(outcome_name)
    except ValueError:
        return _contract_violation_or_invalid_outcome(
            text,
            f"invalid structured status envelope: unsupported outcome status '{outcome_name or '<empty>'}'",
            response_contract,
        )

    if status == OutcomeStatus.SKIPPED:
        return _contract_violation_or_invalid_outcome(
            text,
            "invalid structured status envelope: unsupported outcome status 'skipped'",
            response_contract,
        )

    return ModeledOutcomeParseResult(
        outcome=Outcome(
            status=status,
            preferred_label=preferred_label,
            suggested_next_ids=list(suggested_next_ids),
            context_updates=dict(context_updates),
            notes=notes or "",
            failure_reason=failure_reason or "",
            retryable=retryable,
            failure_kind=FailureKind.BUSINESS
            if has_response_contract(response_contract) and status == OutcomeStatus.FAIL
            else None,
            raw_response_text=raw_text,
        )
    )


def has_response_contract(response_contract: str) -> bool:
    return bool(str(response_contract).strip())


def build_contract_repair_prompt(violation: StructuredContractViolation) -> str:
    lines = [
        f"Your previous final answer violated the {violation.response_contract} response contract.",
        f"Validation error: {violation.reason}",
        "",
        "Re-emit only a corrected final answer for the same decision.",
        "Do not do new repository work.",
        "Do not run commands.",
        "Do not change the substantive decision, routing label, or context updates except as required to satisfy the response contract.",
    ]
    allowed_keys = tuple(violation.write_contract.allowed_keys) if violation.write_contract is not None else ()
    if allowed_keys:
        lines.append(
            'Re-emit the same decision using only these "context_updates" keys when needed: '
            f"{format_status_envelope_allowed_keys(violation.write_contract)}."
        )
    else:
        lines.append('Re-emit the same decision with no "context_updates".')
    lines.extend(
        [
            build_status_envelope_context_updates_contract_text(violation.write_contract),
            "",
            "Previous invalid final answer:",
            violation.raw_text,
        ]
    )
    return "\n".join(lines)


def contract_failure_outcome(violation: StructuredContractViolation) -> Outcome:
    return Outcome(
        status=OutcomeStatus.FAIL,
        notes=violation.raw_text,
        failure_reason=violation.reason,
        failure_kind=FailureKind.CONTRACT,
        raw_response_text=violation.raw_text,
    )


def extract_structured_outcome_payload(
    text: str,
    *,
    require_contract: bool = False,
) -> tuple[dict[str, object] | None, str | None]:
    stripped = text.strip()
    if not stripped:
        if require_contract:
            return None, "invalid structured status envelope: empty response"
        return None, None

    candidates = [stripped]
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            inner = "\n".join(lines[1:-1]).strip()
            if inner and inner not in candidates:
                candidates.append(inner)

    validation_errors: list[str] = []
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            if require_contract:
                validation_errors.append(f"invalid structured status envelope: invalid JSON: {exc}")
            continue
        if not isinstance(payload, dict):
            if require_contract:
                validation_errors.append("invalid structured status envelope: expected a JSON object")
            continue
        if "outcome" not in payload:
            if require_contract:
                validation_errors.append('invalid structured status envelope: missing required top-level key "outcome"')
            continue
        if not set(payload.keys()).issubset(_STRUCTURED_OUTCOME_KEYS):
            unexpected = sorted(set(payload.keys()) - _STRUCTURED_OUTCOME_KEYS)
            unexpected_text = ", ".join(unexpected)
            return None, f"invalid structured status envelope: unexpected top-level keys {unexpected_text}"
        return payload, None
    if require_contract and validation_errors:
        return None, validation_errors[-1]
    return None, None


def _invalid_structured_outcome(text: str, reason: str) -> Outcome:
    return Outcome(
        status=OutcomeStatus.FAIL,
        notes=text.strip(),
        failure_reason=reason,
        raw_response_text=text.strip(),
    )


def _contract_violation_or_invalid_outcome(
    text: str,
    reason: str,
    response_contract: str,
) -> Outcome | StructuredContractViolation:
    if has_response_contract(response_contract):
        return StructuredContractViolation(
            response_contract=response_contract,
            raw_text=text.strip(),
            reason=reason,
        )
    return _invalid_structured_outcome(text, reason)


__all__ = [
    "ModeledOutcomeParseResult",
    "PlainTextParseResult",
    "StructuredContractViolation",
    "build_contract_repair_prompt",
    "coerce_structured_text_outcome",
    "contract_failure_outcome",
    "extract_structured_outcome_payload",
    "has_response_contract",
    "validate_write_contract_violation",
    "with_write_contract",
]
