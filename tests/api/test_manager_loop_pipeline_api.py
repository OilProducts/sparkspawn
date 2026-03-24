from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.api._support import wait_for_pipeline_completion
from tests.support.flow_fixtures import seed_flow_fixture


def test_pipeline_flow_name_resolves_relative_manager_child_paths_from_parent_flow_dir(
    attractor_api_client: TestClient,
    tmp_path: Path,
) -> None:
    flows_dir = tmp_path / "flows"
    flows_dir.mkdir(parents=True, exist_ok=True)
    seed_flow_fixture(flows_dir, "supervision/implementation-worker.dot", as_name="test-supervision/implementation-worker.dot")
    seed_flow_fixture(flows_dir, "supervision/supervised-manager.dot", as_name="test-supervision/supervised-manager.dot")
    workdir = tmp_path / "project"
    workdir.mkdir(parents=True, exist_ok=True)

    response = attractor_api_client.post(
        "/pipelines",
        json={
            "flow_name": "test-supervision/supervised-manager.dot",
            "working_directory": str(workdir),
            "backend": "codex-app-server",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "started"

    final_payload = wait_for_pipeline_completion(attractor_api_client, payload["run_id"])

    assert final_payload["status"] == "completed"
    assert final_payload["outcome"] == "success"
