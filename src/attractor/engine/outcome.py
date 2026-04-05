from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class OutcomeStatus(str, Enum):
    SUCCESS = "success"
    RETRY = "retry"
    FAIL = "fail"
    PARTIAL_SUCCESS = "partial_success"
    SKIPPED = "skipped"


class FailureKind(str, Enum):
    BUSINESS = "business"
    CONTRACT = "contract"
    RUNTIME = "runtime"


@dataclass
class Outcome:
    status: OutcomeStatus
    preferred_label: str = ""
    suggested_next_ids: List[str] = field(default_factory=list)
    context_updates: Dict[str, Any] = field(default_factory=dict)
    failure_reason: str = ""
    notes: str = ""
    retryable: Optional[bool] = None
    failure_kind: Optional[FailureKind] = None
    raw_response_text: str = ""

    def to_payload(self) -> Dict[str, Any]:
        payload = {
            "status": self.status.value,
            "preferred_label": self.preferred_label,
            "suggested_next_ids": list(self.suggested_next_ids),
            "context_updates": dict(self.context_updates),
            "notes": self.notes,
            "failure_reason": self.failure_reason,
        }
        if self.failure_kind is not None:
            payload["failure_kind"] = self.failure_kind.value
        return payload
