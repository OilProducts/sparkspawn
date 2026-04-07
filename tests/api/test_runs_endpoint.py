from __future__ import annotations

import asyncio
import json
from pathlib import Path
import time

import pytest
from fastapi.testclient import TestClient

import workspace.project_chat as project_chat
import workspace.project_chat_models as project_chat_models
import workspace.triggers as workspace_triggers
import attractor.api.server as server
from tests.api._support import (
    close_task_immediately as _close_task_immediately,
    start_pipeline as _start_pipeline,
    wait_for_pipeline_completion as _wait_for_pipeline_completion,
)
from tests.support.flow_fixtures import seed_flow_fixture


TEST_PLANNING_FLOW = "test-planning.dot"
TEST_DISPATCH_FLOW = "test-dispatch.dot"


def _seed_flow(name: str) -> None:
    seed_flow_fixture(server.get_settings().flows_dir, "minimal-valid.dot", as_name=name)


def _seed_planning_flow(name: str) -> None:
    seed_flow_fixture(server.get_settings().flows_dir, "planning-worker.dot", as_name=name)


def _seed_dispatch_flow(name: str) -> None:
    seed_flow_fixture(server.get_settings().flows_dir, "dispatch-worker.dot", as_name=name)


class _DisconnectImmediatelyRequest:
    async def is_disconnected(self) -> bool:
        return True


class _DisconnectAfterEventChecksRequest:
    def __init__(self, *, checks: int) -> None:
        self._checks = checks
        self._count = 0

    async def is_disconnected(self) -> bool:
        self._count += 1
        return self._count > self._checks


class _QueueOnlyRunListEventHub:
    def __init__(self, queued_events: list[dict] | None = None) -> None:
        self._queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=8)
        for event in queued_events or []:
            self._queue.put_nowait(dict(event))

    async def publish(self, event: dict) -> None:
        await self._queue.put(dict(event))

    def subscribe(self) -> asyncio.Queue[dict]:
        return self._queue

    def unsubscribe(self, queue: asyncio.Queue[dict]) -> None:
        assert queue is self._queue

    def reset(self) -> None:
        pass


def _decode_sse_event(chunk: str | bytes) -> dict:
    text = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
    lines = [line for line in text.splitlines() if line.startswith("data: ")]
    assert lines
    return json.loads(lines[0].removeprefix("data: "))


async def _collect_runs_stream_events(
    *,
    request,
    count: int,
    project_path: str | None = None,
) -> tuple[dict[str, str], list[dict]]:
    response = await server.runs_events(request, project_path=project_path)
    iterator = response.body_iterator
    chunks: list[str | bytes] = []
    try:
        for _ in range(count):
            chunks.append(await anext(iterator))
    finally:
        await iterator.aclose()
    return dict(response.headers), [_decode_sse_event(chunk) for chunk in chunks]


async def _next_run_list_event(queue: asyncio.Queue[dict], *, timeout_seconds: float = 1.0) -> dict:
    return await asyncio.wait_for(queue.get(), timeout=timeout_seconds)


def test_runs_overview_endpoints_are_registered() -> None:
    seen: set[tuple[str, str]] = set()
    for route in server.attractor_app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        for method in methods:
            if method == "GET":
                seen.add((method, path))

    assert ("GET", "/runs") in seen
    assert ("GET", "/runs/events") in seen


def test_list_runs_includes_project_and_git_metadata_fields(
    product_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_id = "run-with-project-metadata"

    server._write_run_meta(
        server.RunRecord(
            run_id=run_id,
            flow_name="Flow",
            status="completed",
            outcome="success",
            outcome_reason_code=None,
            outcome_reason_message=None,
            working_directory=str(tmp_path / "work"),
            model="test-model",
            started_at="2026-01-01T00:00:00Z",
            ended_at="2026-01-01T00:01:00Z",
            project_path=str(tmp_path / "project"),
            git_branch="main",
            git_commit="abc123",
            last_error="",
            token_usage=42,
        )
    )

    response = product_api_client.get("/attractor/runs")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["runs"]) == 1
    run_payload = payload["runs"][0]
    assert run_payload["project_path"] == str(tmp_path / "project")
    assert run_payload["git_branch"] == "main"
    assert run_payload["git_commit"] == "abc123"


def test_list_runs_includes_spec_and_plan_artifact_links_when_available_item_9_6_03(
    product_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_id = "run-with-artifact-links"

    server._write_run_meta(
        server.RunRecord(
            run_id=run_id,
            flow_name="Flow",
            status="completed",
            outcome="success",
            outcome_reason_code=None,
            outcome_reason_message=None,
            working_directory=str(tmp_path / "work"),
            model="test-model",
            started_at="2026-01-01T00:00:00Z",
            ended_at="2026-01-01T00:01:00Z",
            project_path=str(tmp_path / "project"),
            git_branch="main",
            git_commit="abc123",
            spec_id="spec-project-1700000000",
            plan_id="plan-project-1700000000",
        )
    )

    response = product_api_client.get("/attractor/runs")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["runs"]) == 1
    run_payload = payload["runs"][0]
    assert run_payload["spec_id"] == "spec-project-1700000000"
    assert run_payload["plan_id"] == "plan-project-1700000000"


def test_list_runs_filters_durable_history_by_project_item_9_6_01(
    product_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    server._write_run_meta(
        server.RunRecord(
            run_id="run-in-project-root",
            flow_name="Flow A",
            status="completed",
            outcome="success",
            outcome_reason_code=None,
            outcome_reason_message=None,
            working_directory=str(tmp_path / "project-alpha"),
            model="test-model",
            started_at="2026-01-01T00:00:00Z",
            ended_at="2026-01-01T00:01:00Z",
            project_path=str(tmp_path / "project-alpha"),
        )
    )
    server._write_run_meta(
        server.RunRecord(
            run_id="run-in-project-child",
            flow_name="Flow B",
            status="completed",
            outcome="success",
            outcome_reason_code=None,
            outcome_reason_message=None,
            working_directory=str(tmp_path / "project-alpha" / "nested"),
            model="test-model",
            started_at="2026-01-01T00:02:00Z",
            ended_at="2026-01-01T00:03:00Z",
            project_path="",
        )
    )
    server._write_run_meta(
        server.RunRecord(
            run_id="run-in-other-project",
            flow_name="Flow C",
            status="failed",
            outcome=None,
            outcome_reason_code=None,
            outcome_reason_message=None,
            working_directory=str(tmp_path / "project-beta"),
            model="test-model",
            started_at="2026-01-01T00:04:00Z",
            ended_at="2026-01-01T00:05:00Z",
            project_path=str(tmp_path / "project-beta"),
        )
    )

    filtered_response = product_api_client.get(
        "/attractor/runs",
        params={"project_path": str(tmp_path / "project-alpha")},
    )
    assert filtered_response.status_code == 200
    filtered_payload = filtered_response.json()
    filtered_run_ids = {run["run_id"] for run in filtered_payload["runs"]}

    assert filtered_run_ids == {"run-in-project-root", "run-in-project-child"}


def test_list_runs_backfills_missing_timestamps_from_run_log_item_9_6_04(
    product_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_id = "run-with-partial-timestamps"
    server._write_run_meta(
        server.RunRecord(
            run_id=run_id,
            flow_name="Flow",
            status="completed",
            outcome="success",
            outcome_reason_code=None,
            outcome_reason_message=None,
            working_directory=str(tmp_path / "project"),
            model="test-model",
            started_at="",
            ended_at=None,
            project_path=str(tmp_path / "project"),
        )
    )
    run_root = server._run_root(run_id)
    (run_root / "run.log").write_text(
        "\n".join(
            [
                "[2026-01-01 00:10:00 UTC] Starting run",
                "[2026-01-01 00:10:30 UTC] Pipeline success",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    response = product_api_client.get("/attractor/runs")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["runs"]) == 1
    run_payload = payload["runs"][0]
    assert run_payload["started_at"] == "2026-01-01T00:10:00Z"
    assert run_payload["ended_at"] == "2026-01-01T00:10:30Z"


def test_list_runs_reconstructs_timestamp_ordering_from_run_logs_item_9_6_04(
    product_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    older_id = "run-older"
    newer_id = "run-newer"

    for run_id, start_ts, end_ts in [
        (older_id, "2026-01-01 00:00:00", "2026-01-01 00:00:30"),
        (newer_id, "2026-01-01 00:01:00", "2026-01-01 00:01:30"),
    ]:
        server._write_run_meta(
            server.RunRecord(
                run_id=run_id,
                flow_name="Flow",
                status="completed",
                outcome="success",
                outcome_reason_code=None,
                outcome_reason_message=None,
                working_directory=str(tmp_path / "project"),
                model="test-model",
                started_at="",
                ended_at=None,
                project_path=str(tmp_path / "project"),
            )
        )
        run_root = server._run_root(run_id)
        (run_root / "run.log").write_text(
            "\n".join(
                [
                    f"[{start_ts} UTC] Starting run",
                    f"[{end_ts} UTC] Pipeline success",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    response = product_api_client.get("/attractor/runs")
    assert response.status_code == 200
    payload = response.json()
    run_ids = [run["run_id"] for run in payload["runs"]]

    assert run_ids == [newer_id, older_id]


def test_runs_events_snapshot_filters_durable_history_by_project_and_returns_run_record_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    server.configure_runtime_paths(runs_dir=tmp_path / "runs")
    project_alpha = str(tmp_path / "project-alpha")
    project_beta = str(tmp_path / "project-beta")
    server._write_run_meta(
        server.RunRecord(
            run_id="run-in-project-root",
            flow_name="Flow A",
            status="completed",
            outcome="success",
            outcome_reason_code=None,
            outcome_reason_message=None,
            working_directory=project_alpha,
            model="test-model",
            started_at="2026-01-01T00:00:00Z",
            ended_at="2026-01-01T00:01:00Z",
            project_path=project_alpha,
            git_branch="main",
            git_commit="abc123",
        )
    )
    server._write_run_meta(
        server.RunRecord(
            run_id="run-in-project-child",
            flow_name="Flow B",
            status="completed",
            outcome="success",
            outcome_reason_code=None,
            outcome_reason_message=None,
            working_directory=str(tmp_path / "project-alpha" / "nested"),
            model="test-model",
            started_at="2026-01-01T00:02:00Z",
            ended_at="2026-01-01T00:03:00Z",
            project_path="",
        )
    )
    server._write_run_meta(
        server.RunRecord(
            run_id="run-in-other-project",
            flow_name="Flow C",
            status="failed",
            outcome=None,
            outcome_reason_code=None,
            outcome_reason_message=None,
            working_directory=project_beta,
            model="test-model",
            started_at="2026-01-01T00:04:00Z",
            ended_at="2026-01-01T00:05:00Z",
            project_path=project_beta,
        )
    )

    headers, events = asyncio.run(
        _collect_runs_stream_events(
            request=_DisconnectImmediatelyRequest(),
            count=1,
            project_path=project_alpha,
        )
    )

    assert headers["content-type"].startswith("text/event-stream")
    assert headers["cache-control"] == "no-cache"
    assert headers["connection"] == "keep-alive"
    assert events == [
        {
            "type": "snapshot",
            "runs": [
                {
                    "run_id": "run-in-project-child",
                    "flow_name": "Flow B",
                    "status": "completed",
                    "outcome": "success",
                    "outcome_reason_code": None,
                    "outcome_reason_message": None,
                    "working_directory": str(tmp_path / "project-alpha" / "nested"),
                    "model": "test-model",
                    "started_at": "2026-01-01T00:02:00Z",
                    "ended_at": "2026-01-01T00:03:00Z",
                    "project_path": "",
                    "git_branch": None,
                    "git_commit": None,
                    "spec_id": None,
                    "plan_id": None,
                    "continued_from_run_id": None,
                    "continued_from_node": None,
                    "continued_from_flow_mode": None,
                    "continued_from_flow_name": None,
                    "last_error": "",
                    "token_usage": None,
                },
                {
                    "run_id": "run-in-project-root",
                    "flow_name": "Flow A",
                    "status": "completed",
                    "outcome": "success",
                    "outcome_reason_code": None,
                    "outcome_reason_message": None,
                    "working_directory": project_alpha,
                    "model": "test-model",
                    "started_at": "2026-01-01T00:00:00Z",
                    "ended_at": "2026-01-01T00:01:00Z",
                    "project_path": project_alpha,
                    "git_branch": "main",
                    "git_commit": "abc123",
                    "spec_id": None,
                    "plan_id": None,
                    "continued_from_run_id": None,
                    "continued_from_node": None,
                    "continued_from_flow_mode": None,
                    "continued_from_flow_name": None,
                    "last_error": "",
                    "token_usage": None,
                },
            ],
        }
    ]


def test_runs_events_filters_live_run_upserts_by_project_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    server.configure_runtime_paths(runs_dir=tmp_path / "runs")
    project_alpha = str(tmp_path / "project-alpha")
    project_beta = str(tmp_path / "project-beta")
    selected_record = server.RunRecord(
        run_id="run-alpha",
        flow_name="alpha.dot",
        status="running",
        outcome=None,
        outcome_reason_code=None,
        outcome_reason_message=None,
        working_directory=project_alpha,
        model="test-model",
        started_at="2026-01-01T00:00:00Z",
        project_path=project_alpha,
    )
    server._write_run_meta(selected_record)
    monkeypatch.setattr(
        server,
        "RUNS_EVENT_HUB",
        _QueueOnlyRunListEventHub(
            queued_events=[
                {
                    "type": "run_upsert",
                    "run": server.RunRecord(
                        run_id="run-beta",
                        flow_name="beta.dot",
                        status="running",
                        outcome=None,
                        outcome_reason_code=None,
                        outcome_reason_message=None,
                        working_directory=project_beta,
                        model="test-model",
                        started_at="2026-01-01T00:01:00Z",
                        project_path=project_beta,
                    ).to_dict(),
                },
                {
                    "type": "run_upsert",
                    "run": selected_record.to_dict(),
                },
            ]
        ),
    )

    _, events = asyncio.run(
        _collect_runs_stream_events(
            request=_DisconnectAfterEventChecksRequest(checks=2),
            count=2,
            project_path=project_alpha,
        )
    )

    assert events[0]["type"] == "snapshot"
    assert [run["run_id"] for run in events[0]["runs"]] == ["run-alpha"]
    assert events[1] == {
        "type": "run_upsert",
        "run": selected_record.to_dict(),
    }


def test_run_list_upsert_publishes_on_pipeline_start_metadata_patch_and_cancel_transition(
    attractor_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    server.configure_runtime_paths(runs_dir=tmp_path / "runs")
    monkeypatch.setattr(server.asyncio, "create_task", _close_task_immediately)
    hub = server.RunListEventHub()
    monkeypatch.setattr(server, "RUNS_EVENT_HUB", hub)
    queue = hub.subscribe()

    start_payload = _start_pipeline(attractor_api_client, tmp_path / "work")
    run_id = str(start_payload["run_id"])

    start_event = asyncio.run(_next_run_list_event(queue))
    assert start_event["type"] == "run_upsert"
    assert start_event["run"]["run_id"] == run_id
    assert start_event["run"]["status"] == "running"
    assert start_event["run"]["started_at"]

    metadata_response = attractor_api_client.patch(
        f"/pipelines/{run_id}/metadata",
        json={"spec_id": "spec-123", "plan_id": "plan-123"},
    )
    assert metadata_response.status_code == 200

    metadata_event = asyncio.run(_next_run_list_event(queue))
    assert metadata_event["type"] == "run_upsert"
    assert metadata_event["run"]["run_id"] == run_id
    assert metadata_event["run"]["status"] == "running"
    assert metadata_event["run"]["spec_id"] == "spec-123"
    assert metadata_event["run"]["plan_id"] == "plan-123"

    cancel_response = attractor_api_client.post(f"/pipelines/{run_id}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json() == {"status": "cancel_requested", "pipeline_id": run_id}

    cancel_event = asyncio.run(_next_run_list_event(queue))
    assert cancel_event["type"] == "run_upsert"
    assert cancel_event["run"]["run_id"] == run_id
    assert cancel_event["run"]["status"] == "cancel_requested"
    assert cancel_event["run"]["last_error"] == "cancel_requested_by_user"


def test_run_list_upsert_publishes_on_pipeline_terminal_completion(
    attractor_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    server.configure_runtime_paths(runs_dir=tmp_path / "runs")
    hub = server.RunListEventHub()
    monkeypatch.setattr(server, "RUNS_EVENT_HUB", hub)
    queue = hub.subscribe()

    start_payload = _start_pipeline(attractor_api_client, tmp_path / "work")
    run_id = str(start_payload["run_id"])

    start_event = asyncio.run(_next_run_list_event(queue))
    assert start_event["type"] == "run_upsert"
    assert start_event["run"]["run_id"] == run_id
    assert start_event["run"]["status"] == "running"

    final_payload = _wait_for_pipeline_completion(attractor_api_client, run_id)
    assert final_payload["status"] == "completed"

    completion_event = asyncio.run(_next_run_list_event(queue, timeout_seconds=2.0))
    assert completion_event["type"] == "run_upsert"
    assert completion_event["run"]["run_id"] == run_id
    assert completion_event["run"]["status"] == "completed"
    assert completion_event["run"]["outcome"] == "success"
    assert completion_event["run"]["ended_at"] is not None


def test_run_list_upsert_publishes_when_startup_reconciles_orphaned_active_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    server.configure_runtime_paths(runs_dir=tmp_path / "runs")
    run_id = "run-orphaned-running"
    project_path = str(tmp_path / "project")
    server._write_run_meta(
        server.RunRecord(
            run_id=run_id,
            flow_name="orphaned.dot",
            status="running",
            outcome=None,
            outcome_reason_code=None,
            outcome_reason_message=None,
            working_directory=project_path,
            model="test-model",
            started_at="2026-01-01T00:00:00Z",
            project_path=project_path,
        )
    )
    hub = server.RunListEventHub()
    monkeypatch.setattr(server, "RUNS_EVENT_HUB", hub)
    queue = hub.subscribe()

    with TestClient(server.attractor_app) as client:
        response = client.get("/status")
        assert response.status_code == 200

        reconciled_event = asyncio.run(_next_run_list_event(queue))

    assert reconciled_event["type"] == "run_upsert"
    assert reconciled_event["run"]["run_id"] == run_id
    assert reconciled_event["run"]["status"] == "failed"
    assert "interrupted when the Attractor server stopped before completion" in reconciled_event["run"]["last_error"]


def test_execution_planning_approval_launches_real_pipeline_backed_run(
    product_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_path = str(tmp_path / "project")
    Path(project_path).mkdir(parents=True, exist_ok=True)
    _seed_planning_flow(TEST_PLANNING_FLOW)

    class _Backend:
        def run(  # type: ignore[no-untyped-def]
            self,
            node_id,
            prompt,
            context,
            *,
            response_contract="",
            contract_repair_attempts=0,
            timeout=None,
            model=None,
        ):
            del node_id, prompt, context, response_contract, contract_repair_attempts, timeout, model
            return json.dumps(
                {
                    "title": "Execution plan",
                    "summary": "Plan summary",
                    "objective": "Implement the approved spec edit.",
                    "work_items": [
                        {
                            "id": "work-1",
                            "title": "Update spec",
                            "description": "Apply the approved change.",
                            "acceptance_criteria": ["Spec updated"],
                            "depends_on": [],
                        }
                    ],
                }
            )

    monkeypatch.setattr(
        server,
        "_build_codergen_backend",
        lambda backend_name, working_dir, emit, model=None: _Backend(),
    )

    server.PROJECT_CHAT._write_state(
        project_chat.ConversationState(
            conversation_id="conversation-test",
            project_path=project_path,
            title="Workflow state test",
            created_at="2026-03-11T02:00:00Z",
            updated_at="2026-03-11T02:00:00Z",
            spec_edit_proposals=[
                project_chat.SpecEditProposal(
                    id="proposal-1",
                    created_at="2026-03-11T02:00:00Z",
                    summary="Summary",
                    changes=[project_chat_models.SpecEditProposalChange(path="specs/project.md", before="old", after="new")],
                    status="pending",
                )
            ],
        )
    )

    response = product_api_client.post(
        "/workspace/api/conversations/conversation-test/spec-edit-proposals/proposal-1/approve",
        json={
            "project_path": project_path,
            "flow_source": TEST_PLANNING_FLOW,
        },
    )

    assert response.status_code == 200
    workflow_run_id = response.json()["execution_workflow"]["run_id"]

    terminal_status = "running"
    for _ in range(200):
        pipeline_response = product_api_client.get(f"/attractor/pipelines/{workflow_run_id}")
        assert pipeline_response.status_code == 200
        terminal_status = pipeline_response.json()["status"]
        if terminal_status != "running":
            break
        time.sleep(0.01)
    assert terminal_status == "completed"

    snapshot = {}
    for _ in range(200):
        conversation_response = product_api_client.get(
            "/workspace/api/conversations/conversation-test",
            params={"project_path": project_path},
        )
        assert conversation_response.status_code == 200
        snapshot = conversation_response.json()
        if snapshot["execution_workflow"]["status"] == "idle" and snapshot["execution_cards"]:
            break
        time.sleep(0.01)

    assert snapshot["execution_workflow"]["status"] == "idle"
    assert snapshot["execution_cards"][0]["source_workflow_run_id"] == workflow_run_id

    record = server._read_run_meta(server._run_meta_path(workflow_run_id))
    assert record is not None
    assert record.flow_name == TEST_PLANNING_FLOW
    assert record.project_path == project_chat._normalize_project_path(project_path)
    assert record.status == "completed"
    assert record.plan_id == snapshot["execution_cards"][0]["id"]

    checkpoint_response = product_api_client.get(f"/attractor/pipelines/{workflow_run_id}/checkpoint")
    assert checkpoint_response.status_code == 200
    context_response = product_api_client.get(f"/attractor/pipelines/{workflow_run_id}/context")
    assert context_response.status_code == 200
    artifacts_response = product_api_client.get(f"/attractor/pipelines/{workflow_run_id}/artifacts")
    assert artifacts_response.status_code == 200
    artifact_paths = [entry["path"] for entry in artifacts_response.json()["artifacts"]]
    assert "artifacts/graphviz/pipeline.dot" in artifact_paths
    assert f"logs/{server.EXECUTION_PLANNING_STAGE_ID}/response.md" in artifact_paths


def test_execution_planning_approval_uses_project_trigger_binding_when_present(
    product_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_path = str(tmp_path / "project")
    Path(project_path).mkdir(parents=True, exist_ok=True)
    _seed_planning_flow("custom-plan.dot")

    class _Backend:
        def run(  # type: ignore[no-untyped-def]
            self,
            node_id,
            prompt,
            context,
            *,
            response_contract="",
            contract_repair_attempts=0,
            timeout=None,
            model=None,
        ):
            del node_id, prompt, context, response_contract, contract_repair_attempts, timeout, model
            return json.dumps(
                {
                    "title": "Execution plan",
                    "summary": "Plan summary",
                    "objective": "Implement the approved spec edit.",
                    "work_items": [],
                }
            )

    monkeypatch.setattr(
        server,
        "_build_codergen_backend",
        lambda backend_name, working_dir, emit, model=None: _Backend(),
    )

    product_api_client.post("/workspace/api/projects/register", json={"project_path": project_path})
    protected_trigger, _ = workspace_triggers.create_trigger_definition(
        server.get_settings().config_dir,
        name="Project planning route",
        enabled=True,
        source_type="workspace_event",
        action={
            "flow_name": "custom-plan.dot",
            "project_path": project_path,
            "static_context": {},
        },
        source={"event_name": "spec_edit_approved"},
        protected=True,
    )
    assert protected_trigger.action.flow_name == "custom-plan.dot"

    server.PROJECT_CHAT._write_state(
        project_chat.ConversationState(
            conversation_id="conversation-test",
            project_path=project_path,
            title="Workflow state test",
            created_at="2026-03-11T02:00:00Z",
            updated_at="2026-03-11T02:00:00Z",
            spec_edit_proposals=[
                project_chat.SpecEditProposal(
                    id="proposal-1",
                    created_at="2026-03-11T02:00:00Z",
                    summary="Summary",
                    changes=[project_chat_models.SpecEditProposalChange(path="specs/project.md", before="old", after="new")],
                    status="pending",
                )
            ],
        )
    )

    response = product_api_client.post(
        "/workspace/api/conversations/conversation-test/spec-edit-proposals/proposal-1/approve",
        json={
            "project_path": project_path,
        },
    )

    assert response.status_code == 200
    workflow_run_id = response.json()["execution_workflow"]["run_id"]
    record = server._read_run_meta(server._run_meta_path(workflow_run_id))
    assert record is not None
    assert record.flow_name == "custom-plan.dot"


def test_approved_execution_card_launches_selected_flow_run(
    product_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_path = str(tmp_path / "project")
    Path(project_path).mkdir(parents=True, exist_ok=True)
    _seed_dispatch_flow(TEST_DISPATCH_FLOW)

    class _Backend:
        def run(  # type: ignore[no-untyped-def]
            self,
            node_id,
            prompt,
            context,
            *,
            response_contract="",
            contract_repair_attempts=0,
            timeout=None,
            model=None,
        ):
            del node_id, prompt, context, response_contract, contract_repair_attempts, timeout, model
            return "implemented"

    monkeypatch.setattr(
        server,
        "_build_codergen_backend",
        lambda backend_name, working_dir, emit, model=None: _Backend(),
    )

    server.PROJECT_CHAT._write_state(
        project_chat.ConversationState(
            conversation_id="conversation-test",
            project_path=project_path,
            title="Execution approval test",
            created_at="2026-03-11T02:00:00Z",
            updated_at="2026-03-11T02:00:00Z",
            execution_cards=[
                project_chat.ExecutionCard(
                    id="execution-card-1",
                    title="Execution plan",
                    summary="Plan summary",
                    objective="Implement the approved spec edit.",
                    source_spec_edit_id="spec-edit-1",
                    source_workflow_run_id="workflow-plan-1",
                    created_at="2026-03-11T02:00:00Z",
                    updated_at="2026-03-11T02:00:00Z",
                    status="draft",
                    flow_source=TEST_PLANNING_FLOW,
                    work_items=[],
                    review_feedback=[],
                )
            ],
        )
    )

    response = product_api_client.post(
        "/workspace/api/conversations/conversation-test/execution-cards/execution-card-1/review",
        json={
            "project_path": project_path,
            "disposition": "approved",
            "message": "Approved for dispatch.",
            "flow_source": TEST_DISPATCH_FLOW,
        },
    )

    assert response.status_code == 200

    runs_response = product_api_client.get("/attractor/runs", params={"project_path": project_path})
    assert runs_response.status_code == 200
    runs_payload = runs_response.json()["runs"]
    matching_runs = [run for run in runs_payload if run["plan_id"] == "execution-card-1"]
    assert len(matching_runs) == 1
    launched_run = matching_runs[0]
    assert launched_run["flow_name"] == TEST_DISPATCH_FLOW
    assert launched_run["spec_id"] == "spec-edit-1"

    terminal_status = "running"
    for _ in range(200):
        pipeline_response = product_api_client.get(f"/attractor/pipelines/{launched_run['run_id']}")
        assert pipeline_response.status_code == 200
        terminal_status = pipeline_response.json()["status"]
        if terminal_status != "running":
            break
        time.sleep(0.01)
    assert terminal_status == "completed"

    snapshot_response = product_api_client.get(
        "/workspace/api/conversations/conversation-test",
        params={"project_path": project_path},
    )
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()
    assert snapshot["execution_cards"][0]["status"] == "approved"
    assert snapshot["event_log"][-1]["message"] == (
        f"Dispatched execution card execution-card-1 as run {launched_run['run_id']} using {TEST_DISPATCH_FLOW}."
    )


def test_approved_execution_card_uses_project_trigger_binding_when_present(
    product_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_path = str(tmp_path / "project")
    Path(project_path).mkdir(parents=True, exist_ok=True)
    _seed_dispatch_flow("custom-implement.dot")

    class _Backend:
        def run(  # type: ignore[no-untyped-def]
            self,
            node_id,
            prompt,
            context,
            *,
            response_contract="",
            contract_repair_attempts=0,
            timeout=None,
            model=None,
        ):
            del node_id, prompt, context, response_contract, contract_repair_attempts, timeout, model
            return "implemented"

    monkeypatch.setattr(
        server,
        "_build_codergen_backend",
        lambda backend_name, working_dir, emit, model=None: _Backend(),
    )

    product_api_client.post("/workspace/api/projects/register", json={"project_path": project_path})
    protected_trigger, _ = workspace_triggers.create_trigger_definition(
        server.get_settings().config_dir,
        name="Project execution route",
        enabled=True,
        source_type="workspace_event",
        action={
            "flow_name": "custom-implement.dot",
            "project_path": project_path,
            "static_context": {},
        },
        source={"event_name": "execution_card_approved"},
        protected=True,
    )
    assert protected_trigger.action.flow_name == "custom-implement.dot"

    server.PROJECT_CHAT._write_state(
        project_chat.ConversationState(
            conversation_id="conversation-test",
            project_path=project_path,
            title="Execution approval test",
            created_at="2026-03-11T02:00:00Z",
            updated_at="2026-03-11T02:00:00Z",
            execution_cards=[
                project_chat.ExecutionCard(
                    id="execution-card-1",
                    title="Execution plan",
                    summary="Plan summary",
                    objective="Implement the approved spec edit.",
                    source_spec_edit_id="spec-edit-1",
                    source_workflow_run_id="workflow-plan-1",
                    created_at="2026-03-11T02:00:00Z",
                    updated_at="2026-03-11T02:00:00Z",
                    status="draft",
                    flow_source=TEST_PLANNING_FLOW,
                    work_items=[],
                    review_feedback=[],
                )
            ],
        )
    )

    response = product_api_client.post(
        "/workspace/api/conversations/conversation-test/execution-cards/execution-card-1/review",
        json={
            "project_path": project_path,
            "disposition": "approved",
            "message": "Approved for dispatch.",
        },
    )

    assert response.status_code == 200

    runs_response = product_api_client.get("/attractor/runs", params={"project_path": project_path})
    assert runs_response.status_code == 200
    matching_runs = [run for run in runs_response.json()["runs"] if run["plan_id"] == "execution-card-1"]
    assert len(matching_runs) == 1
    assert matching_runs[0]["flow_name"] == "custom-implement.dot"
