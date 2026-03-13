from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
import threading
from time import gmtime, strftime
from typing import Any, Optional
import uuid


CHAT_SESSION_VERSION = 2


def _iso_now() -> str:
    return strftime("%Y-%m-%dT%H:%M:%SZ", gmtime())


def _normalize_project_path(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return ""
    return str(Path(trimmed).expanduser().resolve(strict=False))


def _as_non_empty_string(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _truncate_text(value: str, limit: int) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: max(0, limit - 1)].rstrip() + "…"


def _derive_conversation_title(turns: list["ConversationTurn"]) -> str:
    for turn in turns:
        if turn.role != "user":
            continue
        title = _truncate_text(turn.content, 64)
        if title:
            return title
    return "New thread"


def _build_conversation_preview(turns: list["ConversationTurn"]) -> Optional[str]:
    for turn in reversed(turns):
        preview = _truncate_text(turn.content, 120)
        if preview:
            return preview
    return None


@dataclass
class ConversationTurn:
    id: str
    role: str
    content: str
    timestamp: str
    status: str = "complete"
    kind: str = "message"
    artifact_id: Optional[str] = None
    parent_turn_id: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "status": self.status,
            "kind": self.kind,
        }
        if self.artifact_id:
            payload["artifact_id"] = self.artifact_id
        if self.parent_turn_id:
            payload["parent_turn_id"] = self.parent_turn_id
        if self.error:
            payload["error"] = self.error
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConversationTurn":
        return cls(
            id=str(payload.get("id", "")),
            role=str(payload.get("role", "assistant")),
            content=str(payload.get("content", "")),
            timestamp=str(payload.get("timestamp", "")),
            status=str(payload.get("status", "complete") or "complete"),
            kind=str(payload.get("kind", "message") or "message"),
            artifact_id=str(payload.get("artifact_id")) if payload.get("artifact_id") is not None else None,
            parent_turn_id=str(payload.get("parent_turn_id")) if payload.get("parent_turn_id") is not None else None,
            error=str(payload.get("error")) if payload.get("error") is not None else None,
        )


@dataclass
class ToolCallRecord:
    id: str
    kind: str
    status: str
    title: str
    command: Optional[str] = None
    output: Optional[str] = None
    file_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "title": self.title,
        }
        if self.command:
            payload["command"] = self.command
        if self.output:
            payload["output"] = self.output
        if self.file_paths:
            payload["file_paths"] = list(self.file_paths)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ToolCallRecord":
        raw_paths = payload.get("file_paths")
        return cls(
            id=str(payload.get("id", "")),
            kind=str(payload.get("kind", "")),
            status=str(payload.get("status", "completed") or "completed"),
            title=str(payload.get("title", "")),
            command=str(payload.get("command")) if payload.get("command") is not None else None,
            output=str(payload.get("output")) if payload.get("output") is not None else None,
            file_paths=[str(path) for path in raw_paths] if isinstance(raw_paths, list) else [],
        )


@dataclass
class ChatTurnLiveEvent:
    kind: str
    content_delta: Optional[str] = None
    message: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_call: Optional[ToolCallRecord] = None
    spec_proposal_payload: Optional[dict[str, Any]] = None


@dataclass
class ChatTurnResult:
    assistant_message: str
    spec_proposal_payloads: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PreparedChatTurn:
    conversation_id: str
    project_path: str
    prompt: str
    model: Optional[str]
    user_turn: "ConversationTurn"
    assistant_turn: "ConversationTurn"


@dataclass
class DynamicToolInvocationResult:
    tool_call: ToolCallRecord
    response: dict[str, Any]
    spec_proposal_payload: Optional[dict[str, Any]] = None


@dataclass
class ConversationTurnEvent:
    id: str
    turn_id: str
    sequence: int
    timestamp: str
    kind: str
    content_delta: Optional[str] = None
    message: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_call: Optional[ToolCallRecord] = None
    artifact_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "turn_id": self.turn_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "kind": self.kind,
        }
        if self.content_delta is not None:
            payload["content_delta"] = self.content_delta
        if self.message is not None:
            payload["message"] = self.message
        if self.tool_call_id is not None:
            payload["tool_call_id"] = self.tool_call_id
        if self.tool_call is not None:
            payload["tool_call"] = self.tool_call.to_dict()
        if self.artifact_id is not None:
            payload["artifact_id"] = self.artifact_id
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConversationTurnEvent":
        return cls(
            id=str(payload.get("id", "")),
            turn_id=str(payload.get("turn_id", "")),
            sequence=int(payload.get("sequence", 0) or 0),
            timestamp=str(payload.get("timestamp", "")),
            kind=str(payload.get("kind", "")),
            content_delta=str(payload.get("content_delta")) if payload.get("content_delta") is not None else None,
            message=str(payload.get("message")) if payload.get("message") is not None else None,
            tool_call_id=str(payload.get("tool_call_id")) if payload.get("tool_call_id") is not None else None,
            tool_call=ToolCallRecord.from_dict(payload.get("tool_call"))
            if isinstance(payload.get("tool_call"), dict)
            else None,
            artifact_id=str(payload.get("artifact_id")) if payload.get("artifact_id") is not None else None,
        )


def _migrate_legacy_turns(raw_turns: list[dict[str, Any]]) -> tuple[list[ConversationTurn], list[ConversationTurnEvent]]:
    turns: list[ConversationTurn] = []
    turn_events: list[ConversationTurnEvent] = []
    last_user_turn_id: Optional[str] = None
    last_assistant_turn_id: Optional[str] = None
    event_sequence_by_turn: dict[str, int] = {}

    for raw_turn in raw_turns:
        if not isinstance(raw_turn, dict):
            continue
        legacy_turn = ConversationTurn.from_dict(raw_turn)
        legacy_tool_call = ToolCallRecord.from_dict(raw_turn["tool_call"]) if isinstance(raw_turn.get("tool_call"), dict) else None
        if legacy_turn.kind == "tool_call" and legacy_tool_call is not None:
            target_turn_id = last_assistant_turn_id
            if target_turn_id is None:
                synthetic_assistant_turn = ConversationTurn(
                    id=f"turn-{uuid.uuid4().hex}",
                    role="assistant",
                    content="",
                    timestamp=legacy_turn.timestamp or _iso_now(),
                    status="complete" if legacy_tool_call.status != "running" else "streaming",
                    parent_turn_id=last_user_turn_id,
                )
                turns.append(synthetic_assistant_turn)
                last_assistant_turn_id = synthetic_assistant_turn.id
                target_turn_id = synthetic_assistant_turn.id
            next_sequence = event_sequence_by_turn.get(target_turn_id, 0) + 1
            event_sequence_by_turn[target_turn_id] = next_sequence
            event_kind = {
                "running": "tool_call_started",
                "failed": "tool_call_failed",
            }.get(legacy_tool_call.status, "tool_call_completed")
            turn_events.append(
                ConversationTurnEvent(
                    id=f"event-{uuid.uuid4().hex}",
                    turn_id=target_turn_id,
                    sequence=next_sequence,
                    timestamp=legacy_turn.timestamp or _iso_now(),
                    kind=event_kind,
                    tool_call_id=legacy_tool_call.id or legacy_turn.id,
                    tool_call=legacy_tool_call,
                )
            )
            continue

        migrated_turn = ConversationTurn(
            id=legacy_turn.id,
            role=legacy_turn.role,
            content=legacy_turn.content,
            timestamp=legacy_turn.timestamp,
            status="streaming" if legacy_turn.id.endswith(":assistant:live") else legacy_turn.status,
            kind=legacy_turn.kind,
            artifact_id=legacy_turn.artifact_id,
            parent_turn_id=legacy_turn.parent_turn_id or last_user_turn_id if legacy_turn.role == "assistant" else legacy_turn.parent_turn_id,
            error=legacy_turn.error,
        )
        turns.append(migrated_turn)
        if migrated_turn.role == "user":
            last_user_turn_id = migrated_turn.id
            last_assistant_turn_id = None
        elif migrated_turn.role == "assistant":
            last_assistant_turn_id = migrated_turn.id

    return turns, turn_events


@dataclass
class WorkflowEvent:
    message: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkflowEvent":
        return cls(
            message=str(payload.get("message", "")),
            timestamp=str(payload.get("timestamp", "")),
        )


@dataclass
class SpecEditProposalChange:
    path: str
    before: str
    after: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "before": self.before,
            "after": self.after,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SpecEditProposalChange":
        return cls(
            path=str(payload.get("path", "")),
            before=str(payload.get("before", "")),
            after=str(payload.get("after", "")),
        )


@dataclass
class SpecEditProposal:
    id: str
    created_at: str
    summary: str
    changes: list[SpecEditProposalChange]
    status: str = "pending"
    canonical_spec_edit_id: Optional[str] = None
    approved_at: Optional[str] = None
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "created_at": self.created_at,
            "summary": self.summary,
            "status": self.status,
            "changes": [change.to_dict() for change in self.changes],
        }
        if self.canonical_spec_edit_id:
            payload["canonical_spec_edit_id"] = self.canonical_spec_edit_id
        if self.approved_at:
            payload["approved_at"] = self.approved_at
        if self.git_branch:
            payload["git_branch"] = self.git_branch
        if self.git_commit:
            payload["git_commit"] = self.git_commit
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SpecEditProposal":
        raw_changes = payload.get("changes")
        changes = [
            SpecEditProposalChange.from_dict(change)
            for change in raw_changes
            if isinstance(change, dict)
        ] if isinstance(raw_changes, list) else []
        return cls(
            id=str(payload.get("id", "")),
            created_at=str(payload.get("created_at", "")),
            summary=str(payload.get("summary", "")),
            changes=changes,
            status=str(payload.get("status", "pending") or "pending"),
            canonical_spec_edit_id=str(payload.get("canonical_spec_edit_id")) if payload.get("canonical_spec_edit_id") is not None else None,
            approved_at=str(payload.get("approved_at")) if payload.get("approved_at") is not None else None,
            git_branch=str(payload.get("git_branch")) if payload.get("git_branch") is not None else None,
            git_commit=str(payload.get("git_commit")) if payload.get("git_commit") is not None else None,
        )


@dataclass
class ExecutionCardReview:
    id: str
    disposition: str
    message: str
    created_at: str
    author: str = "user"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "disposition": self.disposition,
            "message": self.message,
            "created_at": self.created_at,
            "author": self.author,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExecutionCardReview":
        return cls(
            id=str(payload.get("id", "")),
            disposition=str(payload.get("disposition", "")),
            message=str(payload.get("message", "")),
            created_at=str(payload.get("created_at", "")),
            author=str(payload.get("author", "user") or "user"),
        )


@dataclass
class ExecutionCardWorkItem:
    id: str
    title: str
    description: str
    acceptance_criteria: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "acceptance_criteria": list(self.acceptance_criteria),
            "depends_on": list(self.depends_on),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExecutionCardWorkItem":
        raw_acceptance = payload.get("acceptance_criteria")
        raw_depends_on = payload.get("depends_on")
        return cls(
            id=str(payload.get("id", "")),
            title=str(payload.get("title", "")),
            description=str(payload.get("description", "")),
            acceptance_criteria=[str(item) for item in raw_acceptance] if isinstance(raw_acceptance, list) else [],
            depends_on=[str(item) for item in raw_depends_on] if isinstance(raw_depends_on, list) else [],
        )


@dataclass
class ExecutionCard:
    id: str
    title: str
    summary: str
    objective: str
    source_spec_edit_id: str
    source_workflow_run_id: str
    created_at: str
    updated_at: str
    status: str = "draft"
    flow_source: Optional[str] = None
    work_items: list[ExecutionCardWorkItem] = field(default_factory=list)
    review_feedback: list[ExecutionCardReview] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "objective": self.objective,
            "source_spec_edit_id": self.source_spec_edit_id,
            "source_workflow_run_id": self.source_workflow_run_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "work_items": [item.to_dict() for item in self.work_items],
            "review_feedback": [entry.to_dict() for entry in self.review_feedback],
        }
        if self.flow_source:
            payload["flow_source"] = self.flow_source
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExecutionCard":
        raw_items = payload.get("work_items")
        raw_reviews = payload.get("review_feedback")
        return cls(
            id=str(payload.get("id", "")),
            title=str(payload.get("title", "")),
            summary=str(payload.get("summary", "")),
            objective=str(payload.get("objective", "")),
            source_spec_edit_id=str(payload.get("source_spec_edit_id", "")),
            source_workflow_run_id=str(payload.get("source_workflow_run_id", "")),
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", "")),
            status=str(payload.get("status", "draft") or "draft"),
            flow_source=str(payload.get("flow_source")) if payload.get("flow_source") is not None else None,
            work_items=[
                ExecutionCardWorkItem.from_dict(item)
                for item in raw_items
                if isinstance(item, dict)
            ] if isinstance(raw_items, list) else [],
            review_feedback=[
                ExecutionCardReview.from_dict(item)
                for item in raw_reviews
                if isinstance(item, dict)
            ] if isinstance(raw_reviews, list) else [],
        )


@dataclass
class ExecutionWorkflowState:
    run_id: Optional[str] = None
    status: str = "idle"
    error: Optional[str] = None
    flow_source: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
        }
        if self.run_id:
            payload["run_id"] = self.run_id
        if self.error:
            payload["error"] = self.error
        if self.flow_source:
            payload["flow_source"] = self.flow_source
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExecutionWorkflowState":
        return cls(
            run_id=str(payload.get("run_id")) if payload.get("run_id") is not None else None,
            status=str(payload.get("status", "idle") or "idle"),
            error=str(payload.get("error")) if payload.get("error") is not None else None,
            flow_source=str(payload.get("flow_source")) if payload.get("flow_source") is not None else None,
        )


@dataclass(frozen=True)
class ExecutionWorkflowLaunchSpec:
    conversation_id: str
    project_path: str
    proposal_id: str
    spec_id: str
    prompt: str


@dataclass
class ConversationState:
    conversation_id: str
    project_path: str
    title: str = "New thread"
    created_at: str = ""
    updated_at: str = ""
    turns: list[ConversationTurn] = field(default_factory=list)
    turn_events: list[ConversationTurnEvent] = field(default_factory=list)
    event_log: list[WorkflowEvent] = field(default_factory=list)
    spec_edit_proposals: list[SpecEditProposal] = field(default_factory=list)
    execution_cards: list[ExecutionCard] = field(default_factory=list)
    execution_workflow: ExecutionWorkflowState = field(default_factory=ExecutionWorkflowState)

    def persisted_turn_events(self) -> list[ConversationTurnEvent]:
        return [event for event in self.turn_events if event.kind != "assistant_delta"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "project_path": self.project_path,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "turns": [turn.to_dict() for turn in self.turns],
            "turn_events": [event.to_dict() for event in self.persisted_turn_events()],
            "event_log": [entry.to_dict() for entry in self.event_log],
            "spec_edit_proposals": [proposal.to_dict() for proposal in self.spec_edit_proposals],
            "execution_cards": [card.to_dict() for card in self.execution_cards],
            "execution_workflow": self.execution_workflow.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConversationState":
        raw_turns = payload.get("turns")
        raw_turn_events = payload.get("turn_events")
        raw_events = payload.get("event_log")
        raw_proposals = payload.get("spec_edit_proposals")
        raw_cards = payload.get("execution_cards")
        if isinstance(raw_turn_events, list):
            turns = [
                ConversationTurn.from_dict(turn)
                for turn in raw_turns
                if isinstance(turn, dict)
            ] if isinstance(raw_turns, list) else []
            turn_events = [
                ConversationTurnEvent.from_dict(event)
                for event in raw_turn_events
                if isinstance(event, dict)
            ]
        else:
            turns, turn_events = _migrate_legacy_turns(raw_turns if isinstance(raw_turns, list) else [])
        created_at = _as_non_empty_string(payload.get("created_at"))
        updated_at = _as_non_empty_string(payload.get("updated_at"))
        if not created_at:
            created_at = turns[0].timestamp if turns else ""
        if not updated_at:
            updated_at = turns[-1].timestamp if turns else created_at
        return cls(
            conversation_id=str(payload.get("conversation_id", "")),
            project_path=_normalize_project_path(str(payload.get("project_path", ""))),
            title=_as_non_empty_string(payload.get("title")) or _derive_conversation_title(turns),
            created_at=created_at or _iso_now(),
            updated_at=updated_at or created_at or _iso_now(),
            turns=turns,
            turn_events=turn_events,
            event_log=[
                WorkflowEvent.from_dict(entry)
                for entry in raw_events
                if isinstance(entry, dict)
            ] if isinstance(raw_events, list) else [],
            spec_edit_proposals=[
                SpecEditProposal.from_dict(entry)
                for entry in raw_proposals
                if isinstance(entry, dict)
            ] if isinstance(raw_proposals, list) else [],
            execution_cards=[
                ExecutionCard.from_dict(entry)
                for entry in raw_cards
                if isinstance(raw_cards, list) and isinstance(entry, dict)
            ] if isinstance(raw_cards, list) else [],
            execution_workflow=ExecutionWorkflowState.from_dict(payload.get("execution_workflow", {}))
            if isinstance(payload.get("execution_workflow"), dict)
            else ExecutionWorkflowState(),
        )


@dataclass
class ConversationSummary:
    conversation_id: str
    project_path: str
    title: str
    created_at: str
    updated_at: str
    last_message_preview: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "conversation_id": self.conversation_id,
            "project_path": self.project_path,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.last_message_preview:
            payload["last_message_preview"] = self.last_message_preview
        return payload


@dataclass
class ConversationSessionState:
    conversation_id: str
    updated_at: str
    project_path: str
    runtime_project_path: str
    session_version: int = CHAT_SESSION_VERSION
    thread_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "conversation_id": self.conversation_id,
            "updated_at": self.updated_at,
            "project_path": self.project_path,
            "runtime_project_path": self.runtime_project_path,
            "session_version": self.session_version,
        }
        if self.thread_id:
            payload["thread_id"] = self.thread_id
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConversationSessionState":
        return cls(
            conversation_id=str(payload.get("conversation_id", "")),
            updated_at=str(payload.get("updated_at", "")),
            project_path=_normalize_project_path(str(payload.get("project_path", ""))),
            runtime_project_path=_normalize_project_path(str(payload.get("runtime_project_path", ""))),
            session_version=int(payload.get("session_version", 0) or 0),
            thread_id=str(payload.get("thread_id")) if payload.get("thread_id") is not None else None,
        )


class ConversationEventHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}

    def subscribe(self, conversation_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=32)
        with self._lock:
            self._subscribers.setdefault(conversation_id, []).append(queue)
        return queue

    def unsubscribe(self, conversation_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            listeners = self._subscribers.get(conversation_id)
            if not listeners:
                return
            if queue in listeners:
                listeners.remove(queue)
            if not listeners:
                self._subscribers.pop(conversation_id, None)

    async def publish(self, conversation_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            listeners = list(self._subscribers.get(conversation_id, []))
        for queue in listeners:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(payload)
                except asyncio.QueueFull:
                    continue
