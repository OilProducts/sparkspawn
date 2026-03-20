from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


SIMPLE_FLOW = """
digraph G {
    start [shape=Mdiamond]
    done [shape=Msquare]
    start -> done
}
"""


def close_task_immediately(coro: Any) -> object:
    coro.close()

    class _DummyTask:
        pass

    return _DummyTask()


def start_pipeline(
    api_client: TestClient,
    working_directory: Path,
    *,
    flow_content: str = SIMPLE_FLOW,
    backend: str = "codex-app-server",
    launch_context: dict[str, object] | None = None,
) -> dict[str, Any]:
    response = api_client.post(
        "/pipelines",
        json={
            "flow_content": flow_content,
            "working_directory": str(working_directory),
            "backend": backend,
            "launch_context": launch_context,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "started"
    return payload


def wait_for_pipeline_terminal_status(
    api_client: TestClient,
    pipeline_id: str,
    *,
    attempts: int = 400,
    interval_seconds: float = 0.01,
) -> str:
    for _ in range(attempts):
        response = api_client.get(f"/pipelines/{pipeline_id}")
        assert response.status_code == 200
        status = str(response.json()["status"])
        if status != "running":
            return status
        time.sleep(interval_seconds)
    raise AssertionError("timed out waiting for pipeline completion")


def wait_for_pipeline_completion(
    api_client: TestClient,
    pipeline_id: str,
    *,
    attempts: int = 400,
    interval_seconds: float = 0.01,
) -> dict[str, Any]:
    for _ in range(attempts):
        response = api_client.get(f"/pipelines/{pipeline_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] != "running":
            return payload
        time.sleep(interval_seconds)
    raise AssertionError("timed out waiting for pipeline completion")
