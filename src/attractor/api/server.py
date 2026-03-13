from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import threading
import uuid
import os
import shutil
import re
import sys
import time
from datetime import datetime
from pathlib import Path
import subprocess
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import AliasChoices, BaseModel, Field

from attractor.dsl import (
    canonicalize_dot,
    DotParseError,
    Diagnostic,
    DiagnosticSeverity,
    parse_dot,
    validate_graph,
)
from attractor.engine import (
    Checkpoint,
    Context,
    Outcome,
    OutcomeStatus,
    PipelineExecutor,
    load_checkpoint,
    save_checkpoint,
)
from attractor.graphviz_export import export_graphviz_artifact
from attractor.config import Settings, resolve_settings, validate_settings
from attractor.api.codex_backends import (
    LocalCodexAppServerBackend,
    LocalCodexCliBackend,
    build_codergen_backend as _build_codergen_backend_impl,
)
from attractor.api.flow_sources import (
    ensure_flows_dir as _ensure_flows_dir_impl,
    load_execution_planning_flow_content as _load_execution_planning_flow_content_impl,
    load_flow_content as _load_flow_content_impl,
    resolve_flow_path as _resolve_flow_path_impl,
    semantic_signature as _semantic_signature_impl,
)
from attractor.api.run_records import (
    RunRecord,
    extract_token_usage,
    hydrate_run_record_from_log,
    normalize_run_status,
    run_matches_project_scope,
)
from attractor.api import pipeline_runs
from attractor.api.pipeline_runtime import (
    ActiveRun,
    BroadcastingRunner,
    ConnectionManager,
    ExecutionControl,
    HumanGateBroker,
    PipelineEventHub,
    RuntimeState,
    WebInterviewer,
)
from attractor.api.project_chat import (
    ProjectChatService,
    resolve_runtime_workspace_path,
)
from attractor.api.workspace_api import (
    create_workspace_router,
    WorkspaceApiDependencies,
)
from attractor.storage import (
    build_project_id,
    ensure_project_paths,
    normalize_project_path,
    read_project_paths_by_id,
)
from attractor.handlers import HandlerRunner, build_default_registry
from attractor.handlers.base import CodergenBackend
from attractor.interviewer.base import Interviewer
from attractor.interviewer.models import Answer, AnswerValue, Question
from attractor.transforms import (
    GoalVariableTransform,
    ModelStylesheetTransform,
    TransformPipeline,
)


app = FastAPI()
attractor_app = FastAPI(title="Attractor API")
workspace_app = FastAPI(title="Spark Spawn Workspace API")
attractor_router = APIRouter()
LOGGER = logging.getLogger(__name__)
SETTINGS_LOCK = threading.Lock()
SETTINGS = resolve_settings()
PROJECT_CHAT = ProjectChatService(SETTINGS.data_dir)
REGISTERED_TRANSFORMS: List[object] = []
_REGISTERED_TRANSFORMS_LOCK = threading.Lock()


def get_settings() -> Settings:
    with SETTINGS_LOCK:
        return SETTINGS


def configure_runtime_paths(
    *,
    data_dir: Path | str | None = None,
    runs_dir: Path | str | None = None,
    flows_dir: Path | str | None = None,
    ui_dir: Path | str | None = None,
) -> Settings:
    global SETTINGS, PROJECT_CHAT
    current = get_settings()
    _ = runs_dir
    updated = resolve_settings(
        data_dir=data_dir if data_dir is not None else current.data_dir,
        flows_dir=flows_dir if flows_dir is not None else current.flows_dir,
        ui_dir=ui_dir if ui_dir is not None else current.ui_dir,
    )
    validate_settings(updated)
    with SETTINGS_LOCK:
        SETTINGS = updated
    PROJECT_CHAT = ProjectChatService(updated.data_dir)
    return updated


def validate_runtime_paths() -> None:
    validate_settings(get_settings())


def _resolve_ui_index_path() -> Path | None:
    settings = get_settings()
    if settings.ui_dir:
        index_path = settings.ui_dir / "index.html"
        if index_path.exists():
            return index_path
    if settings.legacy_ui_index and settings.legacy_ui_index.exists():
        return settings.legacy_ui_index
    return None


def _resolve_ui_asset_path(relative_path: str) -> Path | None:
    settings = get_settings()
    if not settings.ui_dir:
        return None
    candidate = settings.ui_dir / relative_path
    if candidate.exists():
        return candidate
    return None


def register_transform(transform: object) -> None:
    with _REGISTERED_TRANSFORMS_LOCK:
        REGISTERED_TRANSFORMS.append(transform)


def clear_registered_transforms() -> None:
    with _REGISTERED_TRANSFORMS_LOCK:
        REGISTERED_TRANSFORMS.clear()


def _registered_transforms_snapshot() -> List[object]:
    with _REGISTERED_TRANSFORMS_LOCK:
        return list(REGISTERED_TRANSFORMS)


manager = ConnectionManager()
HUMAN_BROKER = HumanGateBroker()
EVENT_HUB = PipelineEventHub()
RUNTIME = RuntimeState(last_completed_nodes=[])
ACTIVE_RUNS_LOCK = threading.Lock()
ACTIVE_RUNS: Dict[str, ActiveRun] = {}


RUN_HISTORY_LOCK = threading.Lock()
PIPELINE_LIFECYCLE_PHASES = ("PARSE", "VALIDATE", "INITIALIZE", "EXECUTE", "FINALIZE")


def _runs_root() -> Path:
    return pipeline_runs.runs_root(get_settings)


def _project_runs_dir(project_path: str) -> Optional[Path]:
    return pipeline_runs.project_runs_dir(get_settings, project_path)


def _iter_run_roots(*, project_path: Optional[str] = None) -> list[Path]:
    return pipeline_runs.iter_run_roots(get_settings, project_path=project_path)


def _find_run_root(run_id: str) -> Optional[Path]:
    return pipeline_runs.find_run_root(get_settings, run_id)


def _ensure_run_root_for_project(run_id: str, project_path: str) -> Path:
    return pipeline_runs.ensure_run_root_for_project(get_settings, run_id, project_path)


def _run_root(run_id: str) -> Path:
    return pipeline_runs.run_root(get_settings, run_id)


def _resolve_start_node_id(graph) -> str:
    return pipeline_runs.resolve_start_node_id(graph)


def _graph_attr_context_seed(graph) -> Dict[str, object]:
    return pipeline_runs.graph_attr_context_seed(graph)


def _run_meta_path(run_id: str) -> Path:
    return pipeline_runs.run_meta_path(get_settings, run_id)


def _write_run_meta(record: RunRecord) -> None:
    pipeline_runs.write_run_meta(get_settings, record)


def _read_run_meta(path: Path) -> Optional[RunRecord]:
    return pipeline_runs.read_run_meta(path)


def _record_run_start(
    run_id: str,
    flow_name: str,
    working_directory: str,
    model: str,
    spec_id: Optional[str] = None,
    plan_id: Optional[str] = None,
) -> None:
    pipeline_runs.record_run_start(
        get_settings,
        RUN_HISTORY_LOCK,
        run_id=run_id,
        flow_name=flow_name,
        working_directory=working_directory,
        model=model,
        resolve_runtime_workspace_path=resolve_runtime_workspace_path,
        spec_id=spec_id,
        plan_id=plan_id,
    )


def _ensure_known_pipeline(pipeline_id: str) -> None:
    pipeline_runs.ensure_known_pipeline(get_settings, _get_active_run(pipeline_id), pipeline_id)


def _artifact_media_type(path: Path) -> str:
    return pipeline_runs.artifact_media_type(path)


def _artifact_is_viewable(*, media_type: str, path: Path) -> bool:
    return pipeline_runs.artifact_is_viewable(media_type=media_type, path=path)


def _resolve_artifact_path(run_root: Path, artifact_path: str) -> Path:
    return pipeline_runs.resolve_artifact_path(run_root, artifact_path)


def _list_run_output_artifacts(run_root: Path) -> List[Dict[str, object]]:
    return pipeline_runs.list_run_output_artifacts(run_root)


def _record_run_end(run_id: str, working_directory: str, status: str, last_error: str = "") -> None:
    pipeline_runs.record_run_end(
        get_settings,
        RUN_HISTORY_LOCK,
        run_id=run_id,
        working_directory=working_directory,
        status=status,
        last_error=last_error,
    )


def _record_run_status(run_id: str, status: str, last_error: str = "") -> None:
    pipeline_runs.record_run_status(
        get_settings,
        RUN_HISTORY_LOCK,
        run_id=run_id,
        status=status,
        last_error=last_error,
    )


def _append_run_log(run_id: str, message: str) -> None:
    pipeline_runs.append_run_log(get_settings, run_id, message)


async def _publish_run_event(run_id: str, message: dict) -> None:
    payload = dict(message)
    payload.setdefault("run_id", run_id)
    if payload.get("type") == "log":
        _append_run_log(run_id, str(payload.get("msg", "")))
    await manager.broadcast(payload)
    await EVENT_HUB.publish(run_id, payload)


async def _publish_lifecycle_phase(run_id: str, phase: str) -> None:
    await _publish_run_event(run_id, {"type": "lifecycle", "phase": phase})


def _set_active_run_status(run_id: str, status: str, *, last_error: Optional[str] = None) -> None:
    with ACTIVE_RUNS_LOCK:
        run = ACTIVE_RUNS.get(run_id)
        if not run:
            return
        run.status = status
        if last_error is not None:
            run.last_error = last_error


def _set_active_run_completed_nodes(run_id: str, completed_nodes: List[str]) -> None:
    with ACTIVE_RUNS_LOCK:
        run = ACTIVE_RUNS.get(run_id)
        if not run:
            return
        run.completed_nodes = list(completed_nodes)


def _get_active_run(run_id: str) -> Optional[ActiveRun]:
    with ACTIVE_RUNS_LOCK:
        return ACTIVE_RUNS.get(run_id)


def _read_checkpoint_progress(run_id: str) -> tuple[str, List[str]]:
    return pipeline_runs.read_checkpoint_progress(get_settings, run_id)


def _pipeline_progress_payload(current_node: str, completed_nodes: List[str]) -> Dict[str, object]:
    return pipeline_runs.pipeline_progress_payload(current_node, completed_nodes)


def _pop_active_run(run_id: str) -> Optional[ActiveRun]:
    with ACTIVE_RUNS_LOCK:
        return ACTIVE_RUNS.pop(run_id, None)


class PipelineStartRequest(BaseModel):
    flow_content: str = Field(validation_alias=AliasChoices("flow_content", "dot_source"))
    working_directory: str = "./workspace"
    backend: str = "codex"
    model: Optional[str] = None
    flow_name: Optional[str] = None
    spec_id: Optional[str] = None
    plan_id: Optional[str] = None


class PreviewRequest(BaseModel):
    flow_content: str


class SaveFlowRequest(BaseModel):
    name: str
    content: str
    expect_semantic_equivalence: bool = False


class ResetRequest(BaseModel):
    working_directory: str = "./workspace"


class HumanAnswerRequest(BaseModel):
    selected_value: str


class LegacyHumanAnswerRequest(BaseModel):
    pipeline_id: str
    question_id: str
    selected_value: str


DEFAULT_FLOW = """digraph SoftwareFactory {
    start [shape=Mdiamond, label="Start"];
    setup [shape=box, prompt="Initialize project"];
    build [shape=box, prompt="Build app"];
    done [shape=Msquare, label="Done"];

    start -> setup -> build -> done;
}"""

DEFAULT_EXECUTION_PLANNING_FLOW = "plan-generation.dot"
DEFAULT_EXECUTION_DISPATCH_FLOW = "implement-spec.dot"
EXECUTION_PLANNING_STAGE_ID = "generate_execution_card"


def _build_codergen_backend(
    backend_name: str,
    working_dir: str,
    emit: Callable[[dict], None],
    *,
    model: Optional[str],
) -> CodergenBackend:
    return _build_codergen_backend_impl(
        backend_name,
        working_dir,
        emit,
        model=model,
    )


@app.get("/")
async def get_ui():
    index_path = _resolve_ui_index_path()
    if not index_path:
        raise HTTPException(status_code=404, detail="UI index not found")
    return FileResponse(index_path)


@app.get("/assets/{asset_path:path}")
async def get_frontend_asset(asset_path: str):
    file_path = _resolve_ui_asset_path(f"assets/{asset_path}")
    if not file_path:
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(file_path)


@app.get("/vite.svg")
async def get_frontend_vite_icon():
    file_path = _resolve_ui_asset_path("vite.svg")
    if not file_path:
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(file_path)


@attractor_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@attractor_router.get("/status")
async def get_status():
    return {
        "status": RUNTIME.status,
        "last_error": RUNTIME.last_error,
        "last_working_directory": RUNTIME.last_working_directory,
        "last_model": RUNTIME.last_model,
        "last_completed_nodes": RUNTIME.last_completed_nodes,
        "last_flow_name": RUNTIME.last_flow_name,
        "last_run_id": RUNTIME.last_run_id,
    }


@attractor_router.get("/runs")
async def list_runs(project_path: Optional[str] = None):
    records: List[RunRecord] = []
    for run_dir in _iter_run_roots():
        if not run_dir.is_dir():
            continue
        meta_path = run_dir / "run.json"
        record = _read_run_meta(meta_path)
        if record:
            hydrate_run_record_from_log(record, run_dir)
            records.append(record)
            continue

        run_id = run_dir.name
        record = RunRecord(
            run_id=run_id,
            flow_name="",
            status="unknown",
            result=None,
            working_directory="",
            model="",
            started_at="",
        )
        hydrate_run_record_from_log(record, run_dir)
        records.append(record)

    def _sort_key(item: RunRecord) -> str:
        return item.started_at or item.ended_at or ""

    if project_path:
        records = [record for record in records if run_matches_project_scope(record, project_path)]

    records.sort(key=_sort_key, reverse=True)
    return {"runs": [record.to_dict() for record in records]}


def _graph_payload(graph) -> dict:
    def _attr_value(attrs: Dict[str, object], key: str, default: Optional[object] = None):
        attr = attrs.get(key)
        if attr is None:
            return default
        value = getattr(attr, "value", default)
        if hasattr(value, "raw"):
            return value.raw
        return value

    def _all_attrs_payload(attrs: Dict[str, object]) -> Dict[str, object]:
        return {key: _attr_value(attrs, key) for key in attrs}

    def _merge_extension_attrs(payload: Dict[str, object], attrs: Dict[str, object]) -> Dict[str, object]:
        merged = dict(payload)
        for key, value in _all_attrs_payload(attrs).items():
            if key not in merged:
                merged[key] = value
        return merged

    def _defaults_payload(scope) -> dict:
        return {
            "node": _all_attrs_payload(scope.node),
            "edge": _all_attrs_payload(scope.edge),
        }

    def _subgraph_payload(scope) -> dict:
        return {
            "id": scope.id,
            "attrs": _all_attrs_payload(scope.attrs),
            "node_ids": list(scope.node_ids),
            "defaults": _defaults_payload(scope.defaults),
            "subgraphs": [_subgraph_payload(child) for child in scope.subgraphs],
        }

    return {
        "nodes": [
            _merge_extension_attrs({
                "id": n.node_id,
                "label": _attr_value(n.attrs, "label", n.node_id),
                "shape": _attr_value(n.attrs, "shape"),
                "prompt": _attr_value(n.attrs, "prompt"),
                "tool_command": _attr_value(n.attrs, "tool_command"),
                "tool_hooks.pre": _attr_value(n.attrs, "tool_hooks.pre"),
                "tool_hooks.post": _attr_value(n.attrs, "tool_hooks.post"),
                "join_policy": _attr_value(n.attrs, "join_policy"),
                "error_policy": _attr_value(n.attrs, "error_policy"),
                "max_parallel": _attr_value(n.attrs, "max_parallel"),
                "type": _attr_value(n.attrs, "type"),
                "max_retries": _attr_value(n.attrs, "max_retries"),
                "goal_gate": _attr_value(n.attrs, "goal_gate"),
                "retry_target": _attr_value(n.attrs, "retry_target"),
                "fallback_retry_target": _attr_value(n.attrs, "fallback_retry_target"),
                "fidelity": _attr_value(n.attrs, "fidelity"),
                "thread_id": _attr_value(n.attrs, "thread_id"),
                "class": _attr_value(n.attrs, "class"),
                "timeout": _attr_value(n.attrs, "timeout"),
                "llm_model": _attr_value(n.attrs, "llm_model"),
                "llm_provider": _attr_value(n.attrs, "llm_provider"),
                "reasoning_effort": _attr_value(n.attrs, "reasoning_effort"),
                "auto_status": _attr_value(n.attrs, "auto_status"),
                "allow_partial": _attr_value(n.attrs, "allow_partial"),
                "manager.poll_interval": _attr_value(n.attrs, "manager.poll_interval"),
                "manager.max_cycles": _attr_value(n.attrs, "manager.max_cycles"),
                "manager.stop_condition": _attr_value(n.attrs, "manager.stop_condition"),
                "manager.actions": _attr_value(n.attrs, "manager.actions"),
                "human.default_choice": _attr_value(n.attrs, "human.default_choice"),
            }, n.attrs)
            for n in graph.nodes.values()
        ],
        "graph_attrs": _merge_extension_attrs({
            "goal": _attr_value(graph.graph_attrs, "goal"),
            "label": _attr_value(graph.graph_attrs, "label", ""),
            "model_stylesheet": _attr_value(graph.graph_attrs, "model_stylesheet"),
            "default_max_retry": _attr_value(graph.graph_attrs, "default_max_retry"),
            "retry_target": _attr_value(graph.graph_attrs, "retry_target"),
            "fallback_retry_target": _attr_value(graph.graph_attrs, "fallback_retry_target"),
            "default_fidelity": _attr_value(graph.graph_attrs, "default_fidelity"),
            "stack.child_dotfile": _attr_value(graph.graph_attrs, "stack.child_dotfile"),
            "stack.child_workdir": _attr_value(graph.graph_attrs, "stack.child_workdir"),
            "tool_hooks.pre": _attr_value(graph.graph_attrs, "tool_hooks.pre"),
            "tool_hooks.post": _attr_value(graph.graph_attrs, "tool_hooks.post"),
            "ui_default_llm_model": _attr_value(graph.graph_attrs, "ui_default_llm_model"),
            "ui_default_llm_provider": _attr_value(graph.graph_attrs, "ui_default_llm_provider"),
            "ui_default_reasoning_effort": _attr_value(graph.graph_attrs, "ui_default_reasoning_effort"),
        }, graph.graph_attrs),
        "edges": [
            _merge_extension_attrs({
                "from": e.source,
                "to": e.target,
                "label": _attr_value(e.attrs, "label"),
                "condition": _attr_value(e.attrs, "condition"),
                "weight": _attr_value(e.attrs, "weight"),
                "fidelity": _attr_value(e.attrs, "fidelity"),
                "thread_id": _attr_value(e.attrs, "thread_id"),
                "loop_restart": _attr_value(e.attrs, "loop_restart"),
            }, e.attrs)
            for e in graph.edges
        ],
        "defaults": _defaults_payload(graph.defaults),
        "subgraphs": [_subgraph_payload(subgraph) for subgraph in graph.subgraphs],
    }


def _diagnostic_payload(diagnostic: Diagnostic) -> dict:
    payload = {
        "rule": diagnostic.rule_id,
        "rule_id": diagnostic.rule_id,
        "severity": diagnostic.severity.value,
        "message": diagnostic.message,
        "line": diagnostic.line,
        "node": diagnostic.node_id,
        "node_id": diagnostic.node_id,
    }
    if diagnostic.edge is not None:
        payload["edge"] = list(diagnostic.edge)
    if diagnostic.fix is not None:
        payload["fix"] = diagnostic.fix
    return payload


def _build_transform_pipeline() -> TransformPipeline:
    pipeline = TransformPipeline()
    pipeline.register(GoalVariableTransform())
    pipeline.register(ModelStylesheetTransform())
    for transform in _registered_transforms_snapshot():
        pipeline.register(transform)
    return pipeline


@attractor_router.post("/preview")
async def preview_pipeline(req: PreviewRequest):
    try:
        graph = parse_dot(req.flow_content)
    except DotParseError as exc:
        parse_diag = {
            "rule": "parse_error",
            "rule_id": "parse_error",
            "severity": DiagnosticSeverity.ERROR.value,
            "message": str(exc),
            "line": getattr(exc, "line", 0),
            "node": None,
        }
        return {
            "status": "parse_error",
            "error": str(exc),
            "diagnostics": [parse_diag],
            "errors": [parse_diag],
        }

    graph = _build_transform_pipeline().apply(graph)

    diagnostics = validate_graph(graph)
    errors = [d for d in diagnostics if d.severity == DiagnosticSeverity.ERROR]

    payload = {
        "status": "ok" if not errors else "validation_error",
        "graph": _graph_payload(graph),
        "diagnostics": [_diagnostic_payload(d) for d in diagnostics],
        "errors": [_diagnostic_payload(d) for d in errors],
    }
    return payload


async def _start_pipeline(
    req: PipelineStartRequest,
    *,
    run_id: Optional[str] = None,
    on_complete: Optional[Callable[[str, str], Any]] = None,
) -> dict:
    run_id = (run_id or uuid.uuid4().hex).strip()
    if not run_id:
        run_id = uuid.uuid4().hex
    if _get_active_run(run_id) is not None or _read_run_meta(_run_meta_path(run_id)) is not None:
        return {
            "status": "validation_error",
            "error": f"Run id already exists: {run_id}",
        }
    await _publish_lifecycle_phase(run_id, PIPELINE_LIFECYCLE_PHASES[0])
    try:
        graph = parse_dot(req.flow_content)
    except DotParseError as exc:
        RUNTIME.status = "validation_error"
        RUNTIME.last_error = str(exc)
        parse_diag = {
            "rule": "parse_error",
            "rule_id": "parse_error",
            "severity": DiagnosticSeverity.ERROR.value,
            "message": str(exc),
            "line": getattr(exc, "line", 0),
            "node": None,
        }
        if RUNTIME.last_run_id:
            await _publish_run_event(RUNTIME.last_run_id, {"type": "log", "msg": f"❌ Parse error: {exc}"})
        return {
            "status": "validation_error",
            "error": str(exc),
            "diagnostics": [parse_diag],
            "errors": [parse_diag],
        }

    graph = _build_transform_pipeline().apply(graph)

    await _publish_lifecycle_phase(run_id, PIPELINE_LIFECYCLE_PHASES[1])
    diagnostics = validate_graph(graph)
    errors = [d for d in diagnostics if d.severity == DiagnosticSeverity.ERROR]
    diagnostic_payloads = [_diagnostic_payload(d) for d in diagnostics]
    error_payloads = [_diagnostic_payload(d) for d in errors]
    if errors:
        RUNTIME.status = "validation_error"
        RUNTIME.last_error = errors[0].message
        return {
            "status": "validation_error",
            "diagnostics": diagnostic_payloads,
            "errors": error_payloads,
        }

    await _publish_lifecycle_phase(run_id, PIPELINE_LIFECYCLE_PHASES[2])

    os.makedirs(req.working_directory, exist_ok=True)
    working_dir = str(Path(req.working_directory).resolve())
    selected_model = (req.model or "").strip()
    flow_name = (req.flow_name or "").strip()
    display_model = selected_model or "codex default (config/profile)"

    await _publish_run_event(
        run_id,
        {
            "type": "graph",
            **_graph_payload(graph),
        },
    )

    loop = asyncio.get_running_loop()

    def emit(message: dict):
        asyncio.run_coroutine_threadsafe(_publish_run_event(run_id, message), loop)

    try:
        backend = _build_codergen_backend(
            req.backend,
            working_dir,
            emit,
            model=selected_model or None,
        )
    except ValueError as exc:
        return {
            "status": "validation_error",
            "error": str(exc),
        }

    interviewer: Interviewer = WebInterviewer(HUMAN_BROKER, emit, flow_name, run_id)

    registry = build_default_registry(
        codergen_backend=backend,
        interviewer=interviewer,
    )
    runner = BroadcastingRunner(HandlerRunner(graph, registry), emit)

    run_root = _ensure_run_root_for_project(run_id, working_dir)
    checkpoint_file = str(run_root / "state.json")
    logs_root = str(run_root / "logs")
    # NOTE: This artifact render intentionally uses the submitted DOT source.
    # It does not reflect transform/normalization changes applied to `graph`.
    # If post-transform fidelity is required, render from a serialized `graph` instead.
    graphviz_export = export_graphviz_artifact(req.flow_content, run_root)

    context = Context(values=_graph_attr_context_seed(graph))
    run_root.mkdir(parents=True, exist_ok=True)
    Path(logs_root).mkdir(parents=True, exist_ok=True)
    save_checkpoint(
        Path(checkpoint_file),
        Checkpoint(
            current_node=_resolve_start_node_id(graph),
            completed_nodes=[],
            context=dict(context.values),
            retry_counts={},
        ),
    )

    with ACTIVE_RUNS_LOCK:
        ACTIVE_RUNS[run_id] = ActiveRun(
            run_id=run_id,
            flow_name=flow_name,
            working_directory=working_dir,
            model=display_model,
            status="running",
        )

    RUNTIME.status = "running"
    RUNTIME.last_error = ""
    RUNTIME.last_working_directory = working_dir
    RUNTIME.last_model = display_model
    RUNTIME.last_flow_name = flow_name
    RUNTIME.last_run_id = run_id

    _record_run_start(
        run_id,
        flow_name,
        working_dir,
        display_model,
        spec_id=(req.spec_id or "").strip() or None,
        plan_id=(req.plan_id or "").strip() or None,
    )

    await _publish_run_event(run_id, {"type": "runtime", "status": RUNTIME.status})

    await _publish_run_event(
        run_id,
        {
            "type": "run_meta",
            "working_directory": working_dir,
            "model": display_model,
            "flow_name": flow_name,
            "run_id": run_id,
            "graph_dot_path": str(graphviz_export.dot_path),
            "graph_render_path": str(graphviz_export.rendered_path) if graphviz_export.rendered_path else None,
        },
    )
    if graphviz_export.error:
        await _publish_run_event(
            run_id,
            {
                "type": "log",
                "msg": f"[System] Graph render unavailable: {graphviz_export.error}",
            },
        )
    await _publish_run_event(
        run_id,
        {
            "type": "log",
            "msg": f"[System] Launching run {run_id} in {working_dir} with model: {display_model}",
        },
    )

    async def _run():
        final_status = "failed"
        try:
            await _publish_lifecycle_phase(run_id, PIPELINE_LIFECYCLE_PHASES[3])
            active = _get_active_run(run_id)
            control = active.control if active else ExecutionControl()
            executor = PipelineExecutor(
                graph,
                runner,
                logs_root=logs_root,
                checkpoint_file=checkpoint_file,
                control=control.poll,
                on_event=emit,
            )
            result = await asyncio.to_thread(
                executor.run,
                context,
                resume=True,
            )
            final_status = normalize_run_status(result.status)
            _set_active_run_status(run_id, final_status)
            _set_active_run_completed_nodes(run_id, result.completed_nodes)
            RUNTIME.status = final_status
            RUNTIME.last_completed_nodes = result.completed_nodes
            await _publish_run_event(run_id, {"type": "runtime", "status": final_status})
            _record_run_end(run_id, working_dir, final_status)
            await _publish_run_event(run_id, {"type": "log", "msg": f"Pipeline {final_status}"})
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            _set_active_run_status(run_id, "failed", last_error=str(exc))
            RUNTIME.status = "failed"
            RUNTIME.last_error = str(exc)
            await _publish_run_event(run_id, {"type": "runtime", "status": "failed"})
            _record_run_end(run_id, working_dir, "failed", str(exc))
            await _publish_run_event(run_id, {"type": "log", "msg": f"⚠️ Pipeline Failed: {exc}"})
        finally:
            await _publish_lifecycle_phase(run_id, PIPELINE_LIFECYCLE_PHASES[4])
            _pop_active_run(run_id)
            if on_complete is not None:
                try:
                    completion_result = on_complete(run_id, final_status)
                    if asyncio.iscoroutine(completion_result):
                        await completion_result
                except Exception:  # noqa: BLE001
                    LOGGER.exception("pipeline completion callback failed for run %s", run_id)

    asyncio.create_task(_run())
    return {
        "status": "started",
        "pipeline_id": run_id,
        "run_id": run_id,
        "working_directory": working_dir,
        "model": display_model,
        "diagnostics": diagnostic_payloads,
        "errors": error_payloads,
        "graph_dot_path": str(graphviz_export.dot_path),
        "graph_render_path": str(graphviz_export.rendered_path) if graphviz_export.rendered_path else None,
    }


@attractor_router.post("/pipelines")
async def create_pipeline(req: PipelineStartRequest):
    return await _start_pipeline(req)


@attractor_router.post("/run")
async def run_pipeline(req: PipelineStartRequest):
    return await _start_pipeline(req)


@attractor_router.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    checkpoint_current_node, checkpoint_completed_nodes = _read_checkpoint_progress(pipeline_id)
    active = _get_active_run(pipeline_id)
    if active:
        completed_nodes = list(active.completed_nodes) if active.completed_nodes else checkpoint_completed_nodes
        return {
            "pipeline_id": pipeline_id,
            "status": active.status,
            "flow_name": active.flow_name,
            "working_directory": active.working_directory,
            "model": active.model,
            "last_error": active.last_error,
            "completed_nodes": completed_nodes,
            "progress": _pipeline_progress_payload(checkpoint_current_node, completed_nodes),
        }

    record = _read_run_meta(_run_meta_path(pipeline_id))
    if not record:
        raise HTTPException(status_code=404, detail="Unknown pipeline")
    return {
        "pipeline_id": pipeline_id,
        "status": record.status,
        "flow_name": record.flow_name,
        "working_directory": record.working_directory,
        "model": record.model,
        "last_error": record.last_error,
        "completed_nodes": checkpoint_completed_nodes,
        "progress": _pipeline_progress_payload(checkpoint_current_node, checkpoint_completed_nodes),
        "started_at": record.started_at,
        "ended_at": record.ended_at,
        "result": record.result,
    }


@attractor_router.get("/pipelines/{pipeline_id}/checkpoint")
async def get_pipeline_checkpoint(pipeline_id: str):
    _ensure_known_pipeline(pipeline_id)

    checkpoint = load_checkpoint(_run_root(pipeline_id) / "state.json")
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="Checkpoint unavailable")

    return {
        "pipeline_id": pipeline_id,
        "checkpoint": checkpoint.to_dict(),
    }


@attractor_router.get("/pipelines/{pipeline_id}/context")
async def get_pipeline_context(pipeline_id: str):
    _ensure_known_pipeline(pipeline_id)

    checkpoint = load_checkpoint(_run_root(pipeline_id) / "state.json")
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="Context unavailable")

    return {
        "pipeline_id": pipeline_id,
        "context": dict(checkpoint.context),
    }


@attractor_router.get("/pipelines/{pipeline_id}/artifacts")
async def list_pipeline_artifacts(pipeline_id: str):
    _ensure_known_pipeline(pipeline_id)
    run_root = _run_root(pipeline_id)
    return {
        "pipeline_id": pipeline_id,
        "artifacts": _list_run_output_artifacts(run_root),
    }


@attractor_router.get("/pipelines/{pipeline_id}/artifacts/{artifact_path:path}")
async def get_pipeline_artifact_file(pipeline_id: str, artifact_path: str, download: bool = False):
    _ensure_known_pipeline(pipeline_id)
    run_root = _run_root(pipeline_id)
    resolved_artifact_path = _resolve_artifact_path(run_root, artifact_path)
    if not resolved_artifact_path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")

    media_type = _artifact_media_type(resolved_artifact_path)
    if download:
        return FileResponse(
            resolved_artifact_path,
            media_type=media_type,
            filename=resolved_artifact_path.name,
        )
    return FileResponse(resolved_artifact_path, media_type=media_type)


@attractor_router.get("/pipelines/{pipeline_id}/events")
async def pipeline_events(pipeline_id: str, request: Request):
    active = _get_active_run(pipeline_id)
    existing = _read_run_meta(_run_meta_path(pipeline_id))
    if not active and not existing and not EVENT_HUB.history(pipeline_id):
        raise HTTPException(status_code=404, detail="Unknown pipeline")

    queue, history = EVENT_HUB.subscribe_with_history(pipeline_id)

    async def stream():
        try:
            for event in history:
                yield f"data: {json.dumps(event)}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            EVENT_HUB.unsubscribe(pipeline_id, queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@attractor_router.post("/pipelines/{pipeline_id}/cancel")
async def cancel_pipeline(pipeline_id: str):
    active = _get_active_run(pipeline_id)
    if not active:
        if not _read_run_meta(_run_meta_path(pipeline_id)):
            raise HTTPException(status_code=404, detail="Unknown pipeline")
        return {"status": "ignored", "pipeline_id": pipeline_id}
    active.control.request_cancel()
    _set_active_run_status(pipeline_id, "cancel_requested", last_error="cancel_requested_by_user")
    _record_run_status(pipeline_id, "cancel_requested", "cancel_requested_by_user")
    RUNTIME.status = "cancel_requested"
    RUNTIME.last_error = "cancel_requested_by_user"
    await _publish_run_event(pipeline_id, {"type": "runtime", "status": "cancel_requested"})
    await _publish_run_event(
        pipeline_id,
        {"type": "log", "msg": "[System] Cancel requested. Stopping after current node."},
    )
    return {"status": "cancel_requested", "pipeline_id": pipeline_id}


@attractor_router.get("/pipelines/{pipeline_id}/graph")
async def get_pipeline_graph(pipeline_id: str):
    active = _get_active_run(pipeline_id)
    if not active and not _read_run_meta(_run_meta_path(pipeline_id)):
        raise HTTPException(status_code=404, detail="Unknown pipeline")

    graph_svg_path = _run_root(pipeline_id) / "artifacts" / "graphviz" / "pipeline.svg"
    if not graph_svg_path.exists():
        raise HTTPException(status_code=404, detail="Graph visualization unavailable")

    return FileResponse(graph_svg_path, media_type="image/svg+xml")


@attractor_router.get("/pipelines/{pipeline_id}/questions")
async def list_pipeline_questions(pipeline_id: str):
    active = _get_active_run(pipeline_id)
    if not active and not _read_run_meta(_run_meta_path(pipeline_id)):
        raise HTTPException(status_code=404, detail="Unknown pipeline")
    return {"questions": HUMAN_BROKER.list_for_run(pipeline_id)}


@attractor_router.post("/pipelines/{pipeline_id}/questions/{question_id}/answer")
async def submit_pipeline_answer(pipeline_id: str, question_id: str, req: HumanAnswerRequest):
    active = _get_active_run(pipeline_id)
    if not active and not _read_run_meta(_run_meta_path(pipeline_id)):
        raise HTTPException(status_code=404, detail="Unknown pipeline")
    ok = HUMAN_BROKER.answer(pipeline_id, question_id, req.selected_value)
    if not ok:
        raise HTTPException(status_code=404, detail="Unknown question for pipeline")
    return {"status": "accepted", "pipeline_id": pipeline_id, "question_id": question_id}


@attractor_router.post("/answer")
async def answer_pipeline(req: LegacyHumanAnswerRequest):
    return await submit_pipeline_answer(
        req.pipeline_id,
        req.question_id,
        HumanAnswerRequest(selected_value=req.selected_value),
    )


@attractor_router.post("/reset")
async def reset_checkpoint(req: ResetRequest):
    projects_root = get_settings().projects_dir
    if projects_root.exists():
        for runs_dir in projects_root.glob("*/runs"):
            shutil.rmtree(runs_dir, ignore_errors=True)
    return {"status": "reset"}


def _resolve_project_git_branch(directory_path: Path) -> Optional[str]:
    return pipeline_runs.resolve_project_git_branch(directory_path)


def _resolve_project_git_commit(directory_path: Path) -> Optional[str]:
    return pipeline_runs.resolve_project_git_commit(directory_path)


def _resolve_run_project_git_metadata(working_directory: str) -> tuple[str, Optional[str], Optional[str]]:
    return pipeline_runs.resolve_run_project_git_metadata(
        working_directory,
        resolve_runtime_workspace_path=resolve_runtime_workspace_path,
    )


def _pick_directory_with_osascript(prompt: str) -> Path | None:
    escaped_prompt = prompt.replace('"', '\\"')
    completed = subprocess.run(
        [
            "osascript",
            "-e",
            "try",
            "-e",
            f'POSIX path of (choose folder with prompt "{escaped_prompt}")',
            "-e",
            "on error number -128",
            "-e",
            'return "__CANCELED__"',
            "-e",
            "end try",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "Native macOS directory picker failed.").strip()
        raise RuntimeError(message)
    selected_path = completed.stdout.strip()
    if not selected_path or selected_path == "__CANCELED__":
        return None
    return Path(selected_path).expanduser().resolve()


def _pick_directory_with_tk(prompt: str) -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # pragma: no cover - platform-dependent fallback
        raise RuntimeError("Tk directory picker is unavailable.") from exc

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    try:
        selected_path = filedialog.askdirectory(title=prompt, mustexist=True)
    finally:
        root.destroy()
    if not selected_path:
        return None
    return Path(selected_path).expanduser().resolve()


def _pick_project_directory(prompt: str = "Select Spark Spawn project directory") -> Path | None:
    picker_errors: list[str] = []
    if sys.platform == "darwin" and shutil.which("osascript"):
        try:
            return _pick_directory_with_osascript(prompt)
        except RuntimeError as exc:
            picker_errors.append(str(exc))
    try:
        return _pick_directory_with_tk(prompt)
    except RuntimeError as exc:
        picker_errors.append(str(exc))
    raise RuntimeError(picker_errors[-1] if picker_errors else "No native directory picker is available in this runtime.")


def _load_flow_content(flow_source: str) -> str:
    return _load_flow_content_impl(_flows_dir(), flow_source)


def _load_execution_planning_flow_content(flow_source: str, prompt: str) -> str:
    return _load_execution_planning_flow_content_impl(_flows_dir(), flow_source, prompt)


def _read_pipeline_stage_response(run_id: str, stage_id: str) -> str:
    return pipeline_runs.read_pipeline_stage_response(get_settings, run_id, stage_id)


def _record_run_plan_id(run_id: str, plan_id: str) -> None:
    pipeline_runs.record_run_plan_id(get_settings, RUN_HISTORY_LOCK, run_id, plan_id)


async def _launch_execution_planning_pipeline(
    *,
    conversation_id: str,
    proposal_id: str,
    workflow_run_id: str,
    flow_source: str,
    execution_flow_source: str,
    model: Optional[str],
    review_feedback: Optional[str],
) -> None:
    launch_spec = await asyncio.to_thread(
        PROJECT_CHAT.prepare_execution_workflow_launch,
        conversation_id,
        proposal_id,
        review_feedback,
    )

    async def handle_completion(completed_run_id: str, completed_status: str) -> None:
        try:
            if completed_status != "success":
                record = _read_run_meta(_run_meta_path(completed_run_id))
                error = (
                    record.last_error
                    if record is not None and record.last_error.strip()
                    else f"Execution planning pipeline ended with status '{completed_status}'."
                )
                await asyncio.to_thread(
                    PROJECT_CHAT.fail_execution_workflow,
                    conversation_id,
                    completed_run_id,
                    flow_source,
                    error,
                )
                await PROJECT_CHAT.publish_snapshot(conversation_id)
                return

            raw_response = await asyncio.to_thread(
                _read_pipeline_stage_response,
                completed_run_id,
                EXECUTION_PLANNING_STAGE_ID,
            )
            execution_card = await asyncio.to_thread(
                PROJECT_CHAT.complete_execution_workflow,
                conversation_id,
                proposal_id,
                flow_source,
                execution_flow_source,
                completed_run_id,
                raw_response,
            )
            await asyncio.to_thread(_record_run_plan_id, completed_run_id, execution_card.id)
            await PROJECT_CHAT.publish_snapshot(conversation_id)
        except Exception as exc:  # noqa: BLE001
            await asyncio.to_thread(
                PROJECT_CHAT.fail_execution_workflow,
                conversation_id,
                completed_run_id,
                flow_source,
                str(exc),
            )
            await PROJECT_CHAT.publish_snapshot(conversation_id)

    try:
        flow_content = _load_execution_planning_flow_content(flow_source, launch_spec.prompt)
        launch_payload = await _start_pipeline(
            PipelineStartRequest(
                flow_content=flow_content,
                working_directory=launch_spec.project_path,
                backend="codex",
                model=model,
                flow_name=flow_source,
                spec_id=launch_spec.spec_id,
            ),
            run_id=workflow_run_id,
            on_complete=handle_completion,
        )
    except HTTPException as exc:
        await asyncio.to_thread(
            PROJECT_CHAT.fail_execution_workflow,
            conversation_id,
            workflow_run_id,
            flow_source,
            str(exc.detail),
        )
        await PROJECT_CHAT.publish_snapshot(conversation_id)
        raise

    if launch_payload.get("status") != "started":
        error = str(
            launch_payload.get("error")
            or "Execution planning flow could not be started."
        )
        await asyncio.to_thread(
            PROJECT_CHAT.fail_execution_workflow,
            conversation_id,
            workflow_run_id,
            flow_source,
            error,
        )
        await PROJECT_CHAT.publish_snapshot(conversation_id)
        raise HTTPException(status_code=500, detail=error)


async def _launch_execution_card_pipeline(
    *,
    conversation_id: str,
    execution_card_id: str,
    project_path: str,
    flow_source: str,
    model: Optional[str],
    spec_id: str,
    plan_id: str,
) -> str:
    flow_content = _load_flow_content(flow_source)
    launch_payload = await _start_pipeline(
        PipelineStartRequest(
            flow_content=flow_content,
            working_directory=project_path,
            backend="codex",
            model=model,
            flow_name=flow_source,
            spec_id=spec_id,
            plan_id=plan_id,
        ),
    )
    if launch_payload.get("status") != "started":
        error = str(
            launch_payload.get("error")
            or "Execution flow could not be started."
        )
        raise HTTPException(status_code=500, detail=error)
    run_id = str(launch_payload.get("run_id") or "")
    if not run_id:
        raise HTTPException(status_code=500, detail="Execution flow did not return a run id.")
    snapshot = await asyncio.to_thread(
        PROJECT_CHAT.note_execution_card_dispatched,
        conversation_id,
        execution_card_id,
        run_id,
        flow_source,
    )
    await PROJECT_CHAT.publish_snapshot(conversation_id)
    return run_id


WORKSPACE_ROUTER = create_workspace_router(
    WorkspaceApiDependencies(
        get_settings=get_settings,
        get_project_chat=lambda: PROJECT_CHAT,
        resolve_project_git_branch=lambda runtime_path: _resolve_project_git_branch(runtime_path),
        resolve_project_git_commit=lambda runtime_path: _resolve_project_git_commit(runtime_path),
        pick_project_directory=lambda: _pick_project_directory(),
        default_execution_planning_flow=DEFAULT_EXECUTION_PLANNING_FLOW,
        default_execution_dispatch_flow=DEFAULT_EXECUTION_DISPATCH_FLOW,
        launch_execution_planning_pipeline=lambda **kwargs: _launch_execution_planning_pipeline(
            execution_flow_source=DEFAULT_EXECUTION_DISPATCH_FLOW,
            **kwargs,
        ),
        launch_execution_card_pipeline=lambda **kwargs: _launch_execution_card_pipeline(**kwargs),
    )
)


@attractor_router.get("/api/flows")
async def list_flows():
    flows_dir = _flows_dir()
    return [f.name for f in flows_dir.glob("*.dot")]


def _flows_dir() -> Path:
    return _ensure_flows_dir_impl(get_settings().flows_dir)


def _resolve_flow_path(flow_name: str) -> Path:
    return _resolve_flow_path_impl(_flows_dir(), flow_name)


@attractor_router.get("/api/flows/{name}")
async def get_flow(name: str):
    flow_path = _resolve_flow_path(name)
    if not flow_path.exists():
        raise HTTPException(status_code=404, detail="Flow not found.")
    return {"name": flow_path.name, "content": flow_path.read_text(encoding="utf-8")}


def _semantic_signature(dot_content: str) -> str:
    return _semantic_signature_impl(dot_content, _build_transform_pipeline)


@attractor_router.post("/api/flows")
async def save_flow(req: SaveFlowRequest):
    canonical_content: str
    try:
        graph = parse_dot(req.content)
        canonical_content = canonicalize_dot(req.content)
    except DotParseError as exc:
        parse_diag = {
            "rule": "parse_error",
            "rule_id": "parse_error",
            "severity": DiagnosticSeverity.ERROR.value,
            "message": str(exc),
            "line": getattr(exc, "line", 0),
            "node": None,
            "node_id": None,
        }
        raise HTTPException(
            status_code=422,
            detail={
                "status": "parse_error",
                "error": f"invalid DOT: {exc}",
                "diagnostics": [parse_diag],
                "errors": [parse_diag],
            },
        ) from exc

    graph = _build_transform_pipeline().apply(graph)
    diagnostics = validate_graph(graph)
    errors = [d for d in diagnostics if d.severity == DiagnosticSeverity.ERROR]
    if errors:
        diagnostic_payloads = [_diagnostic_payload(d) for d in diagnostics]
        error_payloads = [_diagnostic_payload(d) for d in errors]
        raise HTTPException(
            status_code=422,
            detail={
                "status": "validation_error",
                "error": "validation errors prevent saving this flow",
                "diagnostics": diagnostic_payloads,
                "errors": error_payloads,
            },
        )

    flow_path = _resolve_flow_path(req.name)

    semantic_equivalent_to_existing: bool | None = None
    if flow_path.exists():
        try:
            semantic_equivalent_to_existing = _semantic_signature(flow_path.read_text()) == _semantic_signature(req.content)
        except DotParseError:
            semantic_equivalent_to_existing = None

        if req.expect_semantic_equivalence and semantic_equivalent_to_existing is False:
            raise HTTPException(
                status_code=409,
                detail={
                    "status": "semantic_mismatch",
                    "error": "semantic equivalence check failed: output DOT would change flow behavior",
                },
            )

    flow_path.write_text(canonical_content, encoding="utf-8")
    response: Dict[str, object] = {"status": "saved", "name": flow_path.name}
    if semantic_equivalent_to_existing is not None:
        response["semantic_equivalent_to_existing"] = semantic_equivalent_to_existing
    return response


@attractor_router.delete("/api/flows/{flow_name}")
async def delete_flow(flow_name: str):
    filepath = _resolve_flow_path(flow_name)
    if filepath.exists():
        filepath.unlink()
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Flow not found.")


attractor_app.include_router(attractor_router)
workspace_app.include_router(WORKSPACE_ROUTER)

# Legacy root paths stay available during the split so the current frontend and tests do not break.
app.include_router(attractor_router)
app.include_router(WORKSPACE_ROUTER)

# Canonical boundary-prefixed apps for the next client/state phase.
app.mount("/attractor", attractor_app)
app.mount("/workspace", workspace_app)
