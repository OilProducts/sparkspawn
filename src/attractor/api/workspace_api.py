from __future__ import annotations

import asyncio
import json
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from attractor.config import Settings
from attractor.api.project_chat import ProjectChatService, resolve_runtime_workspace_path
from attractor.storage import (
    delete_project_flow_binding,
    delete_project_record,
    list_project_records,
    normalize_project_path,
    read_project_record,
    set_project_flow_binding,
    update_project_record,
)


class ConversationTurnRequest(BaseModel):
    project_path: str
    message: str
    model: Optional[str] = None


class ProjectRegistrationRequest(BaseModel):
    project_path: str


class ProjectStateUpdateRequest(BaseModel):
    project_path: str
    is_favorite: Optional[bool] = None
    last_accessed_at: Optional[str] = None
    active_conversation_id: Optional[str] = None


class SpecEditApprovalRequest(BaseModel):
    project_path: str
    model: Optional[str] = None
    flow_source: Optional[str] = None


class SpecEditRejectionRequest(BaseModel):
    project_path: str


class ProjectFlowBindingUpsertRequest(BaseModel):
    project_path: str
    flow_name: str


class ExecutionCardReviewRequest(BaseModel):
    project_path: str
    disposition: str
    message: str
    model: Optional[str] = None
    flow_source: Optional[str] = None


@dataclass(frozen=True)
class WorkspaceApiDependencies:
    get_settings: Callable[[], Settings]
    get_project_chat: Callable[[], ProjectChatService]
    resolve_project_git_branch: Callable[[Path], Optional[str]]
    resolve_project_git_commit: Callable[[Path], Optional[str]]
    pick_project_directory: Callable[[], Optional[Path]]
    default_execution_planning_flow: str
    default_execution_dispatch_flow: str
    launch_execution_planning_pipeline: Callable[..., Awaitable[None]]
    launch_execution_card_pipeline: Callable[..., Awaitable[str]]


def create_workspace_router(deps: WorkspaceApiDependencies) -> APIRouter:
    router = APIRouter()
    workspace_flow_triggers = {
        "spec_edit_approved",
        "execution_card_approved",
        "execution_card_rejected",
        "execution_card_revision_requested",
    }

    def _serialize_project_record(project: Any) -> dict[str, object]:
        return {
            "project_id": project.project_id,
            "project_path": project.project_path,
            "display_name": project.display_name,
            "created_at": project.created_at,
            "last_opened_at": project.last_opened_at,
            "last_accessed_at": project.last_accessed_at,
            "is_favorite": project.is_favorite,
            "active_conversation_id": project.active_conversation_id,
            "flow_bindings": dict(project.flow_bindings),
        }

    def _serialize_deleted_project_record(project: Any) -> dict[str, object]:
        return {
            "status": "deleted",
            "project_id": project.project_id,
            "project_path": project.project_path,
            "display_name": project.display_name,
        }

    def _normalize_project_path_or_400(project_path: str) -> str:
        normalized_project_path = normalize_project_path(project_path)
        if not normalized_project_path:
            raise HTTPException(status_code=400, detail="Project path is required.")
        return normalized_project_path

    def _validate_workspace_flow_trigger(trigger: str) -> str:
        normalized_trigger = trigger.strip()
        if normalized_trigger not in workspace_flow_triggers:
            raise HTTPException(status_code=400, detail=f"Unknown workspace flow trigger: {trigger}")
        return normalized_trigger

    async def _resolve_trigger_flow(project_path: str, trigger: str, fallback_flow: str) -> str:
        project = await asyncio.to_thread(read_project_record, deps.get_settings().data_dir, project_path)
        flow_bindings = project.flow_bindings if project is not None else {}
        return (flow_bindings.get(trigger) or "").strip() or fallback_flow

    @router.get("/api/conversations/{conversation_id}")
    async def get_project_conversation(conversation_id: str, project_path: Optional[str] = None):
        try:
            return await asyncio.to_thread(deps.get_project_chat().get_snapshot, conversation_id, project_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown conversation: {conversation_id}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.delete("/api/conversations/{conversation_id}")
    async def delete_project_conversation(conversation_id: str, project_path: str):
        try:
            return await asyncio.to_thread(deps.get_project_chat().delete_conversation, conversation_id, project_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown conversation: {conversation_id}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/projects")
    async def list_projects():
        projects = await asyncio.to_thread(list_project_records, deps.get_settings().data_dir)
        return [_serialize_project_record(project) for project in projects]

    @router.post("/api/projects/register")
    async def register_project(req: ProjectRegistrationRequest):
        normalized_project_path = _normalize_project_path_or_400(req.project_path)
        try:
            project = await asyncio.to_thread(read_project_record, deps.get_settings().data_dir, normalized_project_path)
            if project is None:
                raise ValueError("Unable to register project.")
            return _serialize_project_record(project)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.patch("/api/projects/state")
    async def update_project_state(req: ProjectStateUpdateRequest):
        normalized_project_path = _normalize_project_path_or_400(req.project_path)
        try:
            project = await asyncio.to_thread(
                update_project_record,
                deps.get_settings().data_dir,
                normalized_project_path,
                last_accessed_at=req.last_accessed_at,
                is_favorite=req.is_favorite,
                active_conversation_id=req.active_conversation_id,
            )
            return _serialize_project_record(project)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.delete("/api/projects")
    async def delete_project(project_path: str):
        normalized_project_path = _normalize_project_path_or_400(project_path)
        try:
            deleted = await asyncio.to_thread(
                delete_project_record,
                deps.get_settings().data_dir,
                normalized_project_path,
            )
            return _serialize_deleted_project_record(deleted)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/api/projects/flow-bindings")
    async def get_project_flow_bindings(project_path: str):
        normalized_project_path = _normalize_project_path_or_400(project_path)
        project = await asyncio.to_thread(read_project_record, deps.get_settings().data_dir, normalized_project_path)
        if project is None:
            raise HTTPException(status_code=404, detail="Unknown project.")
        return {
            "project_path": project.project_path,
            "flow_bindings": dict(project.flow_bindings),
        }

    @router.put("/api/projects/flow-bindings/{trigger}")
    async def put_project_flow_binding(trigger: str, req: ProjectFlowBindingUpsertRequest):
        normalized_project_path = _normalize_project_path_or_400(req.project_path)
        normalized_trigger = _validate_workspace_flow_trigger(trigger)
        flow_name = req.flow_name.strip()
        if not flow_name:
            raise HTTPException(status_code=400, detail="Flow name is required.")
        project = await asyncio.to_thread(
            set_project_flow_binding,
            deps.get_settings().data_dir,
            normalized_project_path,
            normalized_trigger,
            flow_name,
        )
        return {
            "project_path": project.project_path,
            "flow_bindings": dict(project.flow_bindings),
        }

    @router.delete("/api/projects/flow-bindings/{trigger}")
    async def remove_project_flow_binding(trigger: str, project_path: str):
        normalized_project_path = _normalize_project_path_or_400(project_path)
        normalized_trigger = _validate_workspace_flow_trigger(trigger)
        project = await asyncio.to_thread(
            delete_project_flow_binding,
            deps.get_settings().data_dir,
            normalized_project_path,
            normalized_trigger,
        )
        return {
            "project_path": project.project_path,
            "flow_bindings": dict(project.flow_bindings),
        }

    @router.get("/api/projects/conversations")
    async def list_project_conversations(project_path: str):
        try:
            return await asyncio.to_thread(deps.get_project_chat().list_conversations, project_path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/conversations/{conversation_id}/events")
    async def project_conversation_events(conversation_id: str, request: Request, project_path: Optional[str] = None):
        project_chat = deps.get_project_chat()
        try:
            snapshot = await asyncio.to_thread(project_chat.get_snapshot, conversation_id, project_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown conversation: {conversation_id}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        queue = project_chat.events().subscribe(conversation_id)

        async def stream():
            try:
                yield f"data: {json.dumps({'type': 'conversation_snapshot', 'state': snapshot})}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15.0)
                        yield f"data: {json.dumps(event)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                project_chat.events().unsubscribe(conversation_id, queue)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    @router.post("/api/conversations/{conversation_id}/turns")
    async def send_project_conversation_turn(conversation_id: str, req: ConversationTurnRequest):
        loop = asyncio.get_running_loop()
        project_chat = deps.get_project_chat()

        def publish_progress_event(event: dict[str, Any]) -> None:
            asyncio.run_coroutine_threadsafe(
                project_chat.events().publish(
                    conversation_id,
                    event,
                ),
                loop,
            )

        try:
            snapshot = await asyncio.to_thread(
                project_chat.start_turn,
                conversation_id,
                req.project_path,
                req.message,
                req.model,
                publish_progress_event,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return snapshot

    @router.post("/api/conversations/{conversation_id}/spec-edit-proposals/{proposal_id}/approve")
    async def approve_project_spec_edit_proposal(
        conversation_id: str,
        proposal_id: str,
        req: SpecEditApprovalRequest,
    ):
        normalized_project_path = _normalize_project_path_or_400(req.project_path)
        effective_flow_source = (
            (req.flow_source or "").strip()
            or await _resolve_trigger_flow(
                normalized_project_path,
                "spec_edit_approved",
                deps.default_execution_planning_flow,
            )
        )
        try:
            snapshot, proposal = await asyncio.to_thread(
                deps.get_project_chat().approve_spec_edit,
                conversation_id,
                normalized_project_path,
                proposal_id,
            )
            workflow_run_id = f"workflow-{uuid.uuid4().hex[:12]}"
            snapshot = await asyncio.to_thread(
                deps.get_project_chat().mark_execution_workflow_started,
                conversation_id,
                workflow_run_id,
                effective_flow_source,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip() if exc.stderr else str(exc)
            raise HTTPException(status_code=500, detail=f"Failed to commit approved spec edit: {detail}") from exc

        await deps.launch_execution_planning_pipeline(
            conversation_id=conversation_id,
            proposal_id=proposal.id,
            workflow_run_id=workflow_run_id,
            flow_source=effective_flow_source,
            model=req.model,
            review_feedback=None,
        )
        await deps.get_project_chat().publish_snapshot(conversation_id)
        return snapshot

    @router.post("/api/conversations/{conversation_id}/spec-edit-proposals/{proposal_id}/reject")
    async def reject_project_spec_edit_proposal(
        conversation_id: str,
        proposal_id: str,
        req: SpecEditRejectionRequest,
    ):
        normalized_project_path = _normalize_project_path_or_400(req.project_path)
        try:
            snapshot = await asyncio.to_thread(
                deps.get_project_chat().reject_spec_edit,
                conversation_id,
                normalized_project_path,
                proposal_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await deps.get_project_chat().publish_snapshot(conversation_id)
        return snapshot

    @router.post("/api/conversations/{conversation_id}/execution-cards/{execution_card_id}/review")
    async def review_project_execution_card(
        conversation_id: str,
        execution_card_id: str,
        req: ExecutionCardReviewRequest,
    ):
        if req.disposition not in {"approved", "rejected", "revision_requested"}:
            raise HTTPException(status_code=400, detail="Execution card disposition must be approved, rejected, or revision_requested.")
        normalized_project_path = _normalize_project_path_or_400(req.project_path)
        review_flow_source = None
        if req.disposition != "approved":
            planning_trigger = (
                "execution_card_revision_requested"
                if req.disposition == "revision_requested"
                else "execution_card_rejected"
            )
            review_flow_source = await _resolve_trigger_flow(
                normalized_project_path,
                planning_trigger,
                deps.default_execution_planning_flow,
            )
        try:
            snapshot, execution_card, proposal_id, workflow_run_id = await asyncio.to_thread(
                deps.get_project_chat().review_execution_card,
                conversation_id,
                normalized_project_path,
                execution_card_id,
                req.disposition,
                req.message,
                review_flow_source,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await deps.get_project_chat().publish_snapshot(conversation_id)
        if req.disposition == "approved":
            persisted_execution_flow = (execution_card.flow_source or "").strip()
            if not persisted_execution_flow or persisted_execution_flow == deps.default_execution_planning_flow:
                persisted_execution_flow = deps.default_execution_dispatch_flow
            effective_flow_source = (
                (req.flow_source or "").strip()
                or await _resolve_trigger_flow(
                    normalized_project_path,
                    "execution_card_approved",
                    persisted_execution_flow or deps.default_execution_dispatch_flow,
                )
                or persisted_execution_flow
                or deps.default_execution_dispatch_flow
            )
            await deps.launch_execution_card_pipeline(
                conversation_id=conversation_id,
                execution_card_id=execution_card.id,
                project_path=normalized_project_path,
                flow_source=effective_flow_source,
                model=req.model,
                spec_id=execution_card.source_spec_edit_id,
                plan_id=execution_card.id,
            )
        elif proposal_id and workflow_run_id:
            await deps.launch_execution_planning_pipeline(
                conversation_id=conversation_id,
                proposal_id=proposal_id,
                workflow_run_id=workflow_run_id,
                flow_source=review_flow_source or deps.default_execution_planning_flow,
                model=req.model,
                review_feedback=req.message,
            )
        return snapshot

    @router.get("/api/projects/metadata")
    async def get_project_metadata(directory: str):
        requested_path = directory.strip()
        if not requested_path:
            raise HTTPException(status_code=400, detail="Project directory path is required.")

        project_path = Path(requested_path).expanduser()
        if not project_path.is_absolute():
            raise HTTPException(status_code=400, detail="Project directory path must be absolute.")

        normalized_path = project_path.resolve(strict=False)
        runtime_path = Path(resolve_runtime_workspace_path(str(normalized_path)))
        return {
            "name": normalized_path.name or str(normalized_path),
            "directory": str(normalized_path),
            "branch": deps.resolve_project_git_branch(runtime_path),
            "commit": deps.resolve_project_git_commit(runtime_path),
        }

    @router.post("/api/projects/pick-directory")
    async def pick_project_directory():
        try:
            selected_directory = await asyncio.to_thread(deps.pick_project_directory)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if selected_directory is None:
            return {"status": "canceled"}
        if not selected_directory.is_absolute():
            raise HTTPException(status_code=500, detail="Directory picker returned a non-absolute path.")
        return {
            "status": "selected",
            "directory_path": str(selected_directory),
        }

    return router
