from __future__ import annotations

import uuid
from pathlib import Path
from typing import Callable, Optional

from workspace.project_chat_common import (
    extract_json_object,
    iso_now,
    normalize_project_path_value,
    slugify,
)
from workspace.project_chat_models import (
    ConversationSegment,
    ConversationSegmentSource,
    ConversationState,
    ConversationTurn,
    ExecutionCard,
    ExecutionCardReview,
    ExecutionCardWorkItem,
    ExecutionWorkflowLaunchSpec,
    ExecutionWorkflowState,
    SpecEditProposal,
    SpecEditProposalChange,
)
from workspace.project_chat_storage import ProjectChatRepository


class ProjectChatReviewService:
    def __init__(self, repository: ProjectChatRepository) -> None:
        self._repository = repository

    def persist_spec_edit_proposal(
        self,
        state: ConversationState,
        parent_turn: ConversationTurn,
        spec_proposal_payload: dict[str, object],
        *,
        assistant_message_fallback: str = "",
    ) -> Optional[tuple[SpecEditProposal, ConversationSegment]]:
        raw_changes = spec_proposal_payload.get("changes")
        changes = [
            SpecEditProposalChange.from_dict(change)
            for change in raw_changes
            if isinstance(change, dict)
        ] if isinstance(raw_changes, list) else []
        if not changes:
            return None

        summary = str(spec_proposal_payload.get("summary", "")).strip() or assistant_message_fallback
        if not summary:
            summary = "Draft spec edit proposal"

        proposals_by_id = {proposal.id: proposal for proposal in state.spec_edit_proposals}
        for segment in state.segments:
            if segment.turn_id != parent_turn.id or segment.kind != "spec_edit_proposal" or not segment.artifact_id:
                continue
            existing_proposal = proposals_by_id.get(segment.artifact_id)
            if existing_proposal is None:
                continue
            if existing_proposal.summary != summary:
                continue
            if len(existing_proposal.changes) != len(changes):
                continue
            if all(
                existing.path == candidate.path
                and existing.before == candidate.before
                and existing.after == candidate.after
                for existing, candidate in zip(existing_proposal.changes, changes)
            ):
                return None

        proposal = SpecEditProposal(
            id=f"proposal-{uuid.uuid4().hex[:12]}",
            created_at=iso_now(),
            summary=summary,
            changes=changes,
            status="pending",
        )
        state.spec_edit_proposals.append(proposal)
        proposal_segment = ConversationSegment(
            id=f"segment-artifact-{proposal.id}",
            turn_id=parent_turn.id,
            order=self._repository.next_turn_segment_order(state, parent_turn.id),
            kind="spec_edit_proposal",
            role="system",
            status="complete",
            timestamp=proposal.created_at,
            updated_at=proposal.created_at,
            artifact_id=proposal.id,
            source=ConversationSegmentSource(),
        )
        self._repository.upsert_segment(state, proposal_segment)
        self._repository.append_event(state, f"Drafted spec edit proposal {proposal.id}.")
        return proposal, proposal_segment

    def create_spec_edit_proposal(
        self,
        conversation_id: str,
        project_path: str,
        spec_proposal_payload: dict[str, object],
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
                raise ValueError("Conversation has no assistant turn that can own a spec proposal.")
            persisted = self.persist_spec_edit_proposal(
                state,
                parent_turn,
                spec_proposal_payload,
                assistant_message_fallback=parent_turn.content,
            )
            if persisted is None:
                raise ValueError("Spec proposal was not created because an identical proposal already exists on the latest assistant turn.")
            proposal, proposal_segment = persisted
            self._repository.touch_conversation_state(state)
            self._repository.write_state(state)
            return {
                "conversation_id": conversation_id,
                "project_path": normalized_project_path,
                "turn_id": parent_turn.id,
                "proposal_id": proposal.id,
                "segment_id": proposal_segment.id,
            }

    def reject_spec_edit(self, conversation_id: str, project_path: str, proposal_id: str) -> dict[str, object]:
        normalized_project_path = normalize_project_path_value(project_path)
        with self._repository._lock:
            state = self._repository.read_state(conversation_id, normalized_project_path)
            if state is None or state.project_path != normalized_project_path:
                raise ValueError("Conversation not found for project.")
            proposal = next((entry for entry in state.spec_edit_proposals if entry.id == proposal_id), None)
            if proposal is None:
                raise ValueError("Unknown spec edit proposal.")
            proposal.status = "rejected"
            self._repository.append_event(state, f"Rejected spec edit proposal {proposal.id}.")
            self._repository.touch_conversation_state(state)
            self._repository.write_state(state)
        return state.to_dict()

    def approve_spec_edit(
        self,
        conversation_id: str,
        project_path: str,
        proposal_id: str,
    ) -> tuple[dict[str, object], SpecEditProposal]:
        normalized_project_path = normalize_project_path_value(project_path)
        with self._repository._lock:
            state = self._repository.read_state(conversation_id, normalized_project_path)
            if state is None or state.project_path != normalized_project_path:
                raise ValueError("Conversation not found for project.")
            proposal = next((entry for entry in state.spec_edit_proposals if entry.id == proposal_id), None)
            if proposal is None:
                raise ValueError("Unknown spec edit proposal.")
            canonical_spec_edit_id = (
                proposal.canonical_spec_edit_id
                or f"spec-edit-{slugify(Path(project_path).name)}-{uuid.uuid4().hex[:8]}"
            )
            proposal.status = "applied"
            proposal.canonical_spec_edit_id = canonical_spec_edit_id
            proposal.approved_at = iso_now()
            self._repository.append_event(
                state,
                f"Approved spec edit proposal {proposal.id} as canonical spec edit {canonical_spec_edit_id}.",
            )
            self._repository.touch_conversation_state(state)
            self._repository.write_state(state)
        return state.to_dict(), proposal

    def mark_execution_workflow_started(
        self,
        conversation_id: str,
        workflow_run_id: str,
        flow_source: Optional[str],
    ) -> dict[str, object]:
        with self._repository._lock:
            state = self._repository.read_state(conversation_id)
            if state is None:
                raise ValueError("Unknown conversation.")
            state.execution_workflow = ExecutionWorkflowState(
                run_id=workflow_run_id,
                status="running",
                error=None,
                flow_source=flow_source,
            )
            if flow_source:
                self._repository.append_event(state, f"Execution planning started ({workflow_run_id}) using {flow_source}.")
            else:
                self._repository.append_event(state, f"Execution planning started ({workflow_run_id}).")
            self._repository.touch_conversation_state(state)
            self._repository.write_state(state)
        return state.to_dict()

    def prepare_execution_workflow_launch(
        self,
        conversation_id: str,
        proposal_id: str,
        review_feedback: Optional[str],
        *,
        build_execution_planning_prompt: Callable[[ConversationState, SpecEditProposal, Optional[str]], str],
    ) -> ExecutionWorkflowLaunchSpec:
        with self._repository._lock:
            state = self._repository.read_state(conversation_id)
            if state is None:
                raise ValueError("Unknown conversation.")
            proposal = next((entry for entry in state.spec_edit_proposals if entry.id == proposal_id), None)
            if proposal is None or not proposal.canonical_spec_edit_id:
                raise ValueError("Approved spec edit proposal was not found.")
            prompt = build_execution_planning_prompt(state, proposal, review_feedback)
            return ExecutionWorkflowLaunchSpec(
                conversation_id=conversation_id,
                project_path=state.project_path,
                proposal_id=proposal.id,
                spec_id=proposal.canonical_spec_edit_id,
                prompt=prompt,
            )

    def complete_execution_workflow(
        self,
        conversation_id: str,
        proposal_id: str,
        flow_source: Optional[str],
        execution_flow_source: Optional[str],
        workflow_run_id: str,
        raw_response: str,
    ) -> ExecutionCard:
        with self._repository._lock:
            state = self._repository.read_state(conversation_id)
            if state is None:
                raise ValueError("Unknown conversation.")
            proposal = next((entry for entry in state.spec_edit_proposals if entry.id == proposal_id), None)
            if proposal is None or not proposal.canonical_spec_edit_id:
                raise ValueError("Approved spec edit proposal was not found.")
            parsed = extract_json_object(raw_response)
            raw_items = parsed.get("work_items")
            work_items = [
                ExecutionCardWorkItem.from_dict(item)
                for item in raw_items
                if isinstance(item, dict)
            ] if isinstance(raw_items, list) else []
            if not work_items:
                raise RuntimeError("Execution planning returned no work items.")
            now = iso_now()
            execution_card = ExecutionCard(
                id=f"execution-card-{uuid.uuid4().hex[:12]}",
                title=str(parsed.get("title", "")).strip() or "Execution plan",
                summary=str(parsed.get("summary", "")).strip() or "Generated execution plan.",
                objective=str(parsed.get("objective", "")).strip() or "Implement the approved spec edit.",
                source_spec_edit_id=proposal.canonical_spec_edit_id,
                source_workflow_run_id=workflow_run_id,
                created_at=now,
                updated_at=now,
                status="draft",
                flow_source=execution_flow_source,
                work_items=work_items,
            )
            state.execution_cards.append(execution_card)
            execution_card_turn = ConversationTurn(
                id=f"turn-{uuid.uuid4().hex}",
                role="system",
                content="",
                timestamp=now,
                kind="execution_card",
                artifact_id=execution_card.id,
            )
            state.turns.append(execution_card_turn)
            self._repository.upsert_segment(
                state,
                ConversationSegment(
                    id=f"segment-artifact-{execution_card.id}",
                    turn_id=execution_card_turn.id,
                    order=1,
                    kind="execution_card",
                    role="system",
                    status="complete",
                    timestamp=now,
                    updated_at=now,
                    artifact_id=execution_card.id,
                    source=ConversationSegmentSource(),
                ),
            )
            if state.execution_workflow.run_id == workflow_run_id:
                state.execution_workflow = ExecutionWorkflowState(
                    run_id=workflow_run_id,
                    status="idle",
                    error=None,
                    flow_source=flow_source,
                )
            self._repository.append_event(state, f"Execution planning completed and produced {execution_card.id}.")
            self._repository.touch_conversation_state(state)
            self._repository.write_state(state)
            return execution_card

    def fail_execution_workflow(
        self,
        conversation_id: str,
        workflow_run_id: str,
        flow_source: Optional[str],
        error: str,
    ) -> dict[str, object]:
        with self._repository._lock:
            state = self._repository.read_state(conversation_id)
            if state is None:
                raise ValueError("Unknown conversation.")
            if state.execution_workflow.run_id == workflow_run_id:
                state.execution_workflow = ExecutionWorkflowState(
                    run_id=workflow_run_id,
                    status="failed",
                    error=error,
                    flow_source=flow_source,
                )
            self._repository.append_event(state, f"Execution planning failed: {error}")
            self._repository.touch_conversation_state(state)
            self._repository.write_state(state)
            return state.to_dict()

    def note_execution_card_dispatched(
        self,
        conversation_id: str,
        execution_card_id: str,
        run_id: str,
        flow_source: Optional[str],
    ) -> dict[str, object]:
        with self._repository._lock:
            state = self._repository.read_state(conversation_id)
            if state is None:
                raise ValueError("Unknown conversation.")
            execution_card = next((entry for entry in state.execution_cards if entry.id == execution_card_id), None)
            if execution_card is None:
                raise ValueError("Unknown execution card.")
            execution_card.updated_at = iso_now()
            if flow_source:
                self._repository.append_event(
                    state,
                    f"Dispatched execution card {execution_card.id} as run {run_id} using {flow_source}.",
                )
            else:
                self._repository.append_event(
                    state,
                    f"Dispatched execution card {execution_card.id} as run {run_id}.",
                )
            self._repository.touch_conversation_state(state)
            self._repository.write_state(state)
            return state.to_dict()

    def review_execution_card(
        self,
        conversation_id: str,
        project_path: str,
        execution_card_id: str,
        disposition: str,
        message: str,
        flow_source: Optional[str],
    ) -> tuple[dict[str, object], ExecutionCard, Optional[str], Optional[str]]:
        normalized_project_path = normalize_project_path_value(project_path)
        trimmed_message = message.strip()
        if not trimmed_message:
            raise ValueError("Review message is required.")
        with self._repository._lock:
            state = self._repository.read_state(conversation_id, normalized_project_path)
            if state is None or state.project_path != normalized_project_path:
                raise ValueError("Conversation not found for project.")
            execution_card = next((entry for entry in state.execution_cards if entry.id == execution_card_id), None)
            if execution_card is None:
                raise ValueError("Unknown execution card.")
            effective_flow_source = flow_source or execution_card.flow_source
            now = iso_now()
            state.turns.append(
                ConversationTurn(
                    id=f"turn-{uuid.uuid4().hex}",
                    role="user",
                    content=trimmed_message,
                    timestamp=now,
                )
            )
            execution_card.review_feedback.append(
                ExecutionCardReview(
                    id=f"review-{uuid.uuid4().hex[:12]}",
                    disposition=disposition,
                    message=trimmed_message,
                    created_at=now,
                )
            )
            if disposition == "approved":
                execution_card.status = "approved"
                execution_card.updated_at = now
                self._repository.append_event(state, f"Approved execution card {execution_card.id}.")
                workflow_run_id = None
                source_proposal_id = None
            else:
                execution_card.status = "revision-requested" if disposition == "revision_requested" else "rejected"
                execution_card.updated_at = now
                workflow_run_id = f"workflow-{uuid.uuid4().hex[:12]}"
                state.execution_workflow = ExecutionWorkflowState(
                    run_id=workflow_run_id,
                    status="running",
                    error=None,
                    flow_source=effective_flow_source,
                )
                source_proposal_id = next(
                    (
                        proposal.id
                        for proposal in reversed(state.spec_edit_proposals)
                        if proposal.canonical_spec_edit_id == execution_card.source_spec_edit_id
                    ),
                    None,
                )
                self._repository.append_event(
                    state,
                    f"{'Requested revision for' if disposition == 'revision_requested' else 'Rejected'} execution card {execution_card.id}; regenerating with reviewer feedback.",
                )
            self._repository.touch_conversation_state(state, title_hint=trimmed_message)
            self._repository.write_state(state)
        return state.to_dict(), execution_card, source_proposal_id, workflow_run_id
