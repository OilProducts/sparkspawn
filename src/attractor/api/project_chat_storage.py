from __future__ import annotations

import json
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any, Optional

from attractor.api.project_chat_common import (
    as_non_empty_string,
    build_conversation_preview,
    derive_conversation_title,
    iso_now,
    normalize_project_path_value,
    resolve_runtime_workspace_path,
    truncate_text,
)
from attractor.api.project_chat_models import (
    CHAT_SESSION_VERSION,
    ConversationSessionState,
    ConversationState,
    ConversationSummary,
    ConversationTurn,
    ConversationTurnEvent,
    ToolCallRecord,
    WorkflowEvent,
)
from attractor.storage import (
    ProjectPaths,
    ensure_project_paths,
    read_project_paths_by_id,
)


class ProjectChatRepository:
    def __init__(self, data_dir: Path, lock: threading.Lock) -> None:
        self._data_dir = data_dir
        self._lock = lock

    def projects_root(self) -> Path:
        root = self._data_dir / "projects"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def project_paths(self, project_path: str) -> ProjectPaths:
        return ensure_project_paths(self._data_dir, project_path)

    def project_paths_for_conversation(
        self,
        conversation_id: str,
        project_path: Optional[str] = None,
    ) -> ProjectPaths:
        if project_path:
            return self.project_paths(project_path)
        candidates: list[ProjectPaths] = []
        for project_root in self.projects_root().iterdir():
            if not project_root.is_dir():
                continue
            project_record = read_project_paths_by_id(self._data_dir, project_root.name)
            if project_record is None:
                continue
            if (project_record.conversations_dir / conversation_id).exists():
                candidates.append(project_record)
        if len(candidates) == 1:
            return candidates[0]
        if not candidates:
            raise FileNotFoundError(conversation_id)
        raise RuntimeError(f"Conversation id is ambiguous across projects: {conversation_id}")

    def conversation_root(self, conversation_id: str, project_path: Optional[str] = None) -> Path:
        project_paths = self.project_paths_for_conversation(conversation_id, project_path)
        root = project_paths.conversations_dir / conversation_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    def conversation_state_path(self, conversation_id: str, project_path: Optional[str] = None) -> Path:
        return self.conversation_root(conversation_id, project_path) / "state.json"

    def conversation_session_path(self, conversation_id: str, project_path: Optional[str] = None) -> Path:
        return self.conversation_root(conversation_id, project_path) / "session.json"

    def conversation_raw_log_path(self, conversation_id: str, project_path: Optional[str] = None) -> Path:
        return self.conversation_root(conversation_id, project_path) / "raw-log.jsonl"

    def workflow_state_path(self, conversation_id: str, project_path: Optional[str] = None) -> Path:
        project_paths = self.project_paths_for_conversation(conversation_id, project_path)
        return project_paths.workflow_dir / f"{conversation_id}.json"

    def proposals_state_path(self, conversation_id: str, project_path: Optional[str] = None) -> Path:
        project_paths = self.project_paths_for_conversation(conversation_id, project_path)
        return project_paths.proposals_dir / f"{conversation_id}.json"

    def execution_cards_state_path(self, conversation_id: str, project_path: Optional[str] = None) -> Path:
        project_paths = self.project_paths_for_conversation(conversation_id, project_path)
        return project_paths.execution_cards_dir / f"{conversation_id}.json"

    def touch_conversation_state(self, state: ConversationState, *, title_hint: Optional[str] = None) -> None:
        if not state.created_at:
            state.created_at = iso_now()
        if title_hint:
            normalized_title_hint = truncate_text(title_hint, 64)
            if state.title == "New thread" or not as_non_empty_string(state.title):
                state.title = normalized_title_hint
        elif not as_non_empty_string(state.title):
            state.title = derive_conversation_title(state.turns)
        if state.title == "New thread":
            derived_title = derive_conversation_title(state.turns)
            if derived_title != "New thread":
                state.title = derived_title
        state.updated_at = iso_now()

    def build_conversation_summary(self, state: ConversationState) -> ConversationSummary:
        return ConversationSummary(
            conversation_id=state.conversation_id,
            project_path=state.project_path,
            title=as_non_empty_string(state.title) or derive_conversation_title(state.turns),
            created_at=state.created_at or iso_now(),
            updated_at=state.updated_at or state.created_at or iso_now(),
            last_message_preview=build_conversation_preview(state.turns),
        )

    def read_state(self, conversation_id: str, project_path: Optional[str] = None) -> Optional[ConversationState]:
        try:
            path = self.conversation_state_path(conversation_id, project_path)
        except (FileNotFoundError, RuntimeError):
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        normalized_project_path = normalize_project_path_value(str(payload.get("project_path", "")))
        workflow_payload = self.read_json_dict(self.workflow_state_path(conversation_id, normalized_project_path))
        proposals_payload = self.read_json_dict(self.proposals_state_path(conversation_id, normalized_project_path))
        execution_cards_payload = self.read_json_dict(self.execution_cards_state_path(conversation_id, normalized_project_path))
        if workflow_payload:
            payload["event_log"] = workflow_payload.get("event_log", [])
            payload["execution_workflow"] = workflow_payload.get("execution_workflow", {})
        if proposals_payload:
            payload["spec_edit_proposals"] = proposals_payload.get("spec_edit_proposals", [])
        if execution_cards_payload:
            payload["execution_cards"] = execution_cards_payload.get("execution_cards", [])
        state = ConversationState.from_dict(payload)
        if not state.conversation_id:
            state.conversation_id = conversation_id
        return state

    def write_state(self, state: ConversationState) -> None:
        project_paths = self.project_paths(state.project_path)
        path = self.conversation_state_path(state.conversation_id, state.project_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conversation_payload = {
            "conversation_id": state.conversation_id,
            "project_path": state.project_path,
            "title": state.title,
            "created_at": state.created_at,
            "updated_at": state.updated_at,
            "turns": [turn.to_dict() for turn in state.turns],
            "turn_events": [event.to_dict() for event in state.persisted_turn_events()],
        }
        path.write_text(json.dumps(conversation_payload, indent=2, sort_keys=True), encoding="utf-8")
        self.write_json(
            self.workflow_state_path(state.conversation_id, state.project_path),
            {
                "conversation_id": state.conversation_id,
                "project_id": project_paths.project_id,
                "project_path": state.project_path,
                "event_log": [entry.to_dict() for entry in state.event_log],
                "execution_workflow": state.execution_workflow.to_dict(),
            },
        )
        self.write_json(
            self.proposals_state_path(state.conversation_id, state.project_path),
            {
                "conversation_id": state.conversation_id,
                "project_id": project_paths.project_id,
                "project_path": state.project_path,
                "spec_edit_proposals": [proposal.to_dict() for proposal in state.spec_edit_proposals],
            },
        )
        self.write_json(
            self.execution_cards_state_path(state.conversation_id, state.project_path),
            {
                "conversation_id": state.conversation_id,
                "project_id": project_paths.project_id,
                "project_path": state.project_path,
                "execution_cards": [card.to_dict() for card in state.execution_cards],
            },
        )

    def read_json_dict(self, path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def append_raw_rpc_log(
        self,
        conversation_id: str,
        project_path: str,
        *,
        direction: str,
        line: str,
    ) -> None:
        path = self.conversation_raw_log_path(conversation_id, project_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": iso_now(),
            "direction": direction,
            "line": line,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def read_session_state(self, conversation_id: str, project_path: Optional[str] = None) -> Optional[ConversationSessionState]:
        try:
            path = self.conversation_session_path(conversation_id, project_path)
        except (FileNotFoundError, RuntimeError):
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        state = ConversationSessionState.from_dict(payload)
        if not state.conversation_id:
            state.conversation_id = conversation_id
        return state

    def write_session_state(self, state: ConversationSessionState) -> None:
        path = self.conversation_session_path(state.conversation_id, state.project_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    def persist_session_thread(
        self,
        conversation_id: str,
        project_path: str,
        thread_id: str,
    ) -> None:
        normalized_project_path = normalize_project_path_value(project_path)
        runtime_project_path = resolve_runtime_workspace_path(normalized_project_path)
        with self._lock:
            session_state = self.read_session_state(conversation_id, normalized_project_path)
            if session_state is None:
                session_state = ConversationSessionState(
                    conversation_id=conversation_id,
                    updated_at=iso_now(),
                    project_path=normalized_project_path,
                    runtime_project_path=runtime_project_path,
                    session_version=CHAT_SESSION_VERSION,
                )
            session_state.thread_id = thread_id
            session_state.project_path = normalized_project_path
            session_state.runtime_project_path = runtime_project_path
            session_state.session_version = CHAT_SESSION_VERSION
            session_state.updated_at = iso_now()
            self.write_session_state(session_state)

    def list_conversations(self, project_path: str) -> list[dict[str, Any]]:
        normalized_project_path = normalize_project_path_value(project_path)
        if not normalized_project_path:
            raise ValueError("Project path is required.")
        project_paths = self.project_paths(normalized_project_path)
        with self._lock:
            summaries: list[ConversationSummary] = []
            for state_path in project_paths.conversations_dir.glob("*/state.json"):
                try:
                    payload = json.loads(state_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(payload, dict):
                    continue
                state = ConversationState.from_dict(payload)
                if state.project_path != normalized_project_path:
                    continue
                summaries.append(self.build_conversation_summary(state))
        summaries.sort(key=lambda entry: entry.updated_at, reverse=True)
        return [summary.to_dict() for summary in summaries]

    def get_snapshot(self, conversation_id: str, project_path: Optional[str] = None) -> dict[str, Any]:
        with self._lock:
            should_write_state = False
            state = self.read_state(conversation_id, project_path)
            if state is None:
                normalized_project_path = normalize_project_path_value(project_path or "")
                if not normalized_project_path:
                    raise FileNotFoundError(conversation_id)
                state = ConversationState(
                    conversation_id=conversation_id,
                    project_path=normalized_project_path,
                )
                self.touch_conversation_state(state)
                should_write_state = True
            elif project_path:
                normalized_project_path = normalize_project_path_value(project_path)
                if normalized_project_path and normalized_project_path != state.project_path:
                    raise ValueError("Conversation is already bound to a different project path.")
            if not state.created_at or not state.updated_at or not as_non_empty_string(state.title):
                if not state.created_at:
                    state.created_at = iso_now()
                if not state.updated_at:
                    state.updated_at = state.created_at
                if not as_non_empty_string(state.title):
                    state.title = derive_conversation_title(state.turns)
                should_write_state = True
            if len(state.persisted_turn_events()) != len(state.turn_events):
                should_write_state = True
            if should_write_state:
                self.write_state(state)
        return state.to_dict()

    def delete_conversation(self, conversation_id: str, project_path: str) -> dict[str, Any]:
        normalized_project_path = normalize_project_path_value(project_path)
        if not normalized_project_path:
            raise ValueError("Project path is required.")

        project_paths = self.project_paths(normalized_project_path)
        conversation_root = project_paths.conversations_dir / conversation_id
        with self._lock:
            state = self.read_state(conversation_id, normalized_project_path)
            if state is None or state.project_path != normalized_project_path:
                raise FileNotFoundError(conversation_id)

        if conversation_root.exists():
            shutil.rmtree(conversation_root)
        for sidecar in (
            project_paths.workflow_dir / f"{conversation_id}.json",
            project_paths.proposals_dir / f"{conversation_id}.json",
            project_paths.execution_cards_dir / f"{conversation_id}.json",
        ):
            sidecar.unlink(missing_ok=True)

        return {
            "status": "deleted",
            "conversation_id": conversation_id,
            "project_path": normalized_project_path,
        }

    def append_event(self, state: ConversationState, message: str) -> None:
        state.event_log.append(WorkflowEvent(message=message, timestamp=iso_now()))

    def next_turn_event_sequence(self, state: ConversationState, turn_id: str) -> int:
        max_sequence = 0
        for event in state.turn_events:
            if event.turn_id == turn_id and event.sequence > max_sequence:
                max_sequence = event.sequence
        return max_sequence + 1

    def append_turn_event(
        self,
        state: ConversationState,
        turn_id: str,
        kind: str,
        *,
        sequence: Optional[int] = None,
        content_delta: Optional[str] = None,
        message: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        tool_call: Optional[ToolCallRecord] = None,
        artifact_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> ConversationTurnEvent:
        event = ConversationTurnEvent(
            id=f"event-{uuid.uuid4().hex}",
            turn_id=turn_id,
            sequence=sequence if sequence is not None else self.next_turn_event_sequence(state, turn_id),
            timestamp=timestamp or iso_now(),
            kind=kind,
            content_delta=content_delta,
            message=message,
            tool_call_id=tool_call_id,
            tool_call=ToolCallRecord.from_dict(tool_call.to_dict()) if tool_call is not None else None,
            artifact_id=artifact_id,
        )
        state.turn_events.append(event)
        return event

    def upsert_turn(self, state: ConversationState, turn: ConversationTurn) -> None:
        for index, existing_turn in enumerate(state.turns):
            if existing_turn.id != turn.id:
                continue
            state.turns[index] = turn
            return
        state.turns.append(turn)

    def get_turn(self, state: ConversationState, turn_id: str) -> Optional[ConversationTurn]:
        for turn in state.turns:
            if turn.id == turn_id:
                return turn
        return None

    def build_turn_upsert_payload(
        self,
        state: ConversationState,
        turn: ConversationTurn,
    ) -> dict[str, Any]:
        serialized_turn = turn.to_dict()
        if (
            turn.role == "assistant"
            and turn.status in {"pending", "streaming"}
            and not as_non_empty_string(turn.content)
        ):
            serialized_turn["content"] = ""
        return {
            "type": "turn_upsert",
            "conversation_id": state.conversation_id,
            "project_path": state.project_path,
            "title": state.title,
            "updated_at": state.updated_at,
            "turn": serialized_turn,
        }

    def build_turn_event_payload(
        self,
        state: ConversationState,
        event: ConversationTurnEvent,
    ) -> dict[str, Any]:
        return {
            "type": "turn_event",
            "conversation_id": state.conversation_id,
            "project_path": state.project_path,
            "title": state.title,
            "updated_at": state.updated_at,
            "event": event.to_dict(),
        }
