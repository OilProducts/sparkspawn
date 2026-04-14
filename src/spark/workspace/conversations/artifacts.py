from __future__ import annotations

import copy
import uuid
from typing import Optional

from spark.workspace.conversations.models import (
    ConversationSegment,
    ConversationSegmentSource,
    ConversationState,
    ConversationTurn,
    FlowLaunch,
    FlowRunRequest,
)
from spark.workspace.conversations.repository import ProjectChatRepository
from spark.workspace.conversations.utils import (
    iso_now,
    normalize_project_path_value,
)


class ProjectChatReviewService:
    def __init__(self, repository: ProjectChatRepository) -> None:
        self._repository = repository

    def persist_flow_run_request(
        self,
        state: ConversationState,
        parent_turn: ConversationTurn,
        flow_run_request_payload: dict[str, object],
    ) -> Optional[tuple[FlowRunRequest, ConversationSegment]]:
        flow_name = str(flow_run_request_payload.get("flow_name", "")).strip()
        summary = str(flow_run_request_payload.get("summary", "")).strip()
        if not flow_name or not summary:
            return None
        goal = str(flow_run_request_payload.get("goal", "")).strip() or None
        launch_context = copy.deepcopy(flow_run_request_payload.get("launch_context")) if isinstance(flow_run_request_payload.get("launch_context"), dict) else None
        model = str(flow_run_request_payload.get("model", "")).strip() or None

        requests_by_id = {request.id: request for request in state.flow_run_requests}
        for segment in state.segments:
            if segment.turn_id != parent_turn.id or segment.kind != "flow_run_request" or not segment.artifact_id:
                continue
            existing_request = requests_by_id.get(segment.artifact_id)
            if existing_request is None:
                continue
            if (
                existing_request.flow_name == flow_name
                and existing_request.summary == summary
                and existing_request.goal == goal
                and existing_request.launch_context == launch_context
                and existing_request.model == model
            ):
                return None

        now = iso_now()
        request = FlowRunRequest(
            id=f"flow-run-request-{uuid.uuid4().hex[:12]}",
            created_at=now,
            updated_at=now,
            flow_name=flow_name,
            summary=summary,
            project_path=state.project_path,
            conversation_id=state.conversation_id,
            source_turn_id=parent_turn.id,
            goal=goal,
            launch_context=launch_context,
            model=model,
        )
        request_segment = ConversationSegment(
            id=f"segment-artifact-{request.id}",
            turn_id=parent_turn.id,
            order=self._repository.next_turn_segment_order(state, parent_turn.id),
            kind="flow_run_request",
            role="system",
            status="complete",
            timestamp=now,
            updated_at=now,
            artifact_id=request.id,
            source=ConversationSegmentSource(),
        )
        request.source_segment_id = request_segment.id
        state.flow_run_requests.append(request)
        self._repository.upsert_segment(state, request_segment)
        self._repository.append_event(state, f"Created flow run request {request.id} for {flow_name}.")
        return request, request_segment

    def create_flow_run_request(
        self,
        conversation_id: str,
        project_path: str,
        flow_run_request_payload: dict[str, object],
    ) -> dict[str, object]:
        normalized_project_path = normalize_project_path_value(project_path)
        with self._repository._lock:
            state = self._repository.read_state(conversation_id, normalized_project_path)
            if state is None or state.project_path != normalized_project_path:
                raise FileNotFoundError(conversation_id)
            parent_turn = next(
                (
                    turn
                    for turn in reversed(state.turns)
                    if turn.role == "assistant" and turn.kind == "message"
                ),
                None,
            )
            if parent_turn is None:
                raise ValueError("Conversation has no assistant turn that can own a flow run request.")
            persisted = self.persist_flow_run_request(state, parent_turn, flow_run_request_payload)
            if persisted is None:
                raise ValueError("Flow run request was not created because an identical request already exists on the latest assistant turn.")
            request, request_segment = persisted
            self._repository.touch_conversation_state(state)
            self._repository.write_state(state)
            return {
                "conversation_id": conversation_id,
                "project_path": normalized_project_path,
                "turn_id": parent_turn.id,
                "flow_run_request_id": request.id,
                "segment_id": request_segment.id,
            }

    def persist_flow_launch(
        self,
        state: ConversationState,
        parent_turn: ConversationTurn,
        flow_launch_payload: dict[str, object],
    ) -> tuple[FlowLaunch, ConversationSegment]:
        flow_name = str(flow_launch_payload.get("flow_name", "")).strip()
        summary = str(flow_launch_payload.get("summary", "")).strip()
        if not flow_name or not summary:
            raise ValueError("Flow launch requires a non-empty flow_name and summary.")
        goal = str(flow_launch_payload.get("goal", "")).strip() or None
        launch_context = copy.deepcopy(flow_launch_payload.get("launch_context")) if isinstance(flow_launch_payload.get("launch_context"), dict) else None
        model = str(flow_launch_payload.get("model", "")).strip() or None

        now = iso_now()
        launch = FlowLaunch(
            id=f"flow-launch-{uuid.uuid4().hex[:12]}",
            created_at=now,
            updated_at=now,
            flow_name=flow_name,
            summary=summary,
            project_path=state.project_path,
            conversation_id=state.conversation_id,
            source_turn_id=parent_turn.id,
            goal=goal,
            launch_context=launch_context,
            model=model,
        )
        launch_segment = ConversationSegment(
            id=f"segment-artifact-{launch.id}",
            turn_id=parent_turn.id,
            order=self._repository.next_turn_segment_order(state, parent_turn.id),
            kind="flow_launch",
            role="system",
            status="complete",
            timestamp=now,
            updated_at=now,
            artifact_id=launch.id,
            source=ConversationSegmentSource(),
        )
        launch.source_segment_id = launch_segment.id
        state.flow_launches.append(launch)
        self._repository.upsert_segment(state, launch_segment)
        self._repository.append_event(state, f"Created direct flow launch {launch.id} for {flow_name}.")
        return launch, launch_segment

    def create_flow_launch(
        self,
        conversation_id: str,
        project_path: str,
        flow_launch_payload: dict[str, object],
    ) -> dict[str, object]:
        normalized_project_path = normalize_project_path_value(project_path)
        with self._repository._lock:
            state = self._repository.read_state(conversation_id, normalized_project_path)
            if state is None or state.project_path != normalized_project_path:
                raise FileNotFoundError(conversation_id)
            parent_turn = next(
                (
                    turn
                    for turn in reversed(state.turns)
                    if turn.role == "assistant" and turn.kind == "message"
                ),
                None,
            )
            if parent_turn is None:
                raise ValueError("Conversation has no assistant turn that can own a direct flow launch.")
            launch, launch_segment = self.persist_flow_launch(state, parent_turn, flow_launch_payload)
            self._repository.touch_conversation_state(state)
            self._repository.write_state(state)
            return {
                "conversation_id": conversation_id,
                "project_path": normalized_project_path,
                "turn_id": parent_turn.id,
                "flow_launch_id": launch.id,
                "segment_id": launch_segment.id,
            }

    def review_flow_run_request(
        self,
        conversation_id: str,
        project_path: str,
        request_id: str,
        disposition: str,
        message: str,
        flow_name: Optional[str],
        model: Optional[str],
    ) -> tuple[dict[str, object], FlowRunRequest]:
        normalized_project_path = normalize_project_path_value(project_path)
        trimmed_message = message.strip()
        if not trimmed_message:
            raise ValueError("Review message is required.")
        with self._repository._lock:
            state = self._repository.read_state(conversation_id, normalized_project_path)
            if state is None or state.project_path != normalized_project_path:
                raise ValueError("Conversation not found for project.")
            request = next((entry for entry in state.flow_run_requests if entry.id == request_id), None)
            if request is None:
                raise ValueError("Unknown flow run request.")
            if request.status not in {"pending", "approved", "launch_failed"}:
                raise ValueError(f"Flow run request is not reviewable in status '{request.status}'.")
            now = iso_now()
            if disposition == "approved":
                request.status = "approved"
                request.review_message = trimmed_message
                request.updated_at = now
                if flow_name:
                    request.flow_name = flow_name
                if model:
                    request.model = model
                self._repository.append_event(state, f"Approved flow run request {request.id}.")
            else:
                request.status = "rejected"
                request.review_message = trimmed_message
                request.updated_at = now
                self._repository.append_event(state, f"Rejected flow run request {request.id}.")
            self._repository.touch_conversation_state(state, title_hint=trimmed_message)
            self._repository.write_state(state)
            return state.to_dict(), request

    def note_flow_launch_started(
        self,
        conversation_id: str,
        launch_id: str,
        run_id: str,
        flow_name: str,
    ) -> dict[str, object]:
        with self._repository._lock:
            state = self._repository.read_state(conversation_id)
            if state is None:
                raise ValueError("Conversation not found.")
            launch = next((entry for entry in state.flow_launches if entry.id == launch_id), None)
            if launch is None:
                raise ValueError("Unknown flow launch.")
            launch.status = "launched"
            launch.updated_at = iso_now()
            launch.run_id = run_id
            launch.flow_name = flow_name
            launch.launch_error = None
            self._repository.append_event(state, f"Launched direct flow {launch.id} as run {run_id} using {flow_name}.")
            self._repository.touch_conversation_state(state)
            self._repository.write_state(state)
            return state.to_dict()

    def fail_flow_launch(
        self,
        conversation_id: str,
        launch_id: str,
        flow_name: str,
        error: str,
    ) -> dict[str, object]:
        with self._repository._lock:
            state = self._repository.read_state(conversation_id)
            if state is None:
                raise ValueError("Conversation not found.")
            launch = next((entry for entry in state.flow_launches if entry.id == launch_id), None)
            if launch is None:
                raise ValueError("Unknown flow launch.")
            launch.status = "launch_failed"
            launch.updated_at = iso_now()
            launch.flow_name = flow_name
            launch.launch_error = error.strip() or "Flow launch failed."
            self._repository.append_event(state, f"Direct flow launch {launch.id} failed for {flow_name}: {launch.launch_error}")
            self._repository.touch_conversation_state(state)
            self._repository.write_state(state)
            return state.to_dict()

    def note_flow_run_request_launched(
        self,
        conversation_id: str,
        request_id: str,
        run_id: str,
        flow_name: str,
    ) -> dict[str, object]:
        with self._repository._lock:
            state = self._repository.read_state(conversation_id)
            if state is None:
                raise ValueError("Unknown conversation.")
            request = next((entry for entry in state.flow_run_requests if entry.id == request_id), None)
            if request is None:
                raise ValueError("Unknown flow run request.")
            request.status = "launched"
            request.run_id = run_id
            request.flow_name = flow_name
            request.launch_error = None
            request.updated_at = iso_now()
            self._repository.append_event(
                state,
                f"Launched flow run request {request.id} as run {run_id} using {flow_name}.",
            )
            self._repository.touch_conversation_state(state)
            self._repository.write_state(state)
            return state.to_dict()

    def fail_flow_run_request_launch(
        self,
        conversation_id: str,
        request_id: str,
        flow_name: str,
        error: str,
    ) -> dict[str, object]:
        with self._repository._lock:
            state = self._repository.read_state(conversation_id)
            if state is None:
                raise ValueError("Unknown conversation.")
            request = next((entry for entry in state.flow_run_requests if entry.id == request_id), None)
            if request is None:
                raise ValueError("Unknown flow run request.")
            request.status = "launch_failed"
            request.flow_name = flow_name
            request.launch_error = error
            request.updated_at = iso_now()
            self._repository.append_event(
                state,
                f"Flow run request {request.id} failed to launch: {error}",
            )
            self._repository.touch_conversation_state(state)
            self._repository.write_state(state)
            return state.to_dict()
