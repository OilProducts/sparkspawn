from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import attractor.api.server as server


def test_attractor_subapp_exposes_status_endpoint(api_client: TestClient) -> None:
    server.RUNTIME.status = "running"
    server.RUNTIME.last_flow_name = "implement-spec.dot"
    server.RUNTIME.last_run_id = "run-123"

    response = api_client.get("/attractor/status")

    assert response.status_code == 200
    assert response.json() == {
        "status": "running",
        "last_error": "",
        "last_working_directory": "",
        "last_model": "",
        "last_completed_nodes": [],
        "last_flow_name": "implement-spec.dot",
        "last_run_id": "run-123",
    }


def test_workspace_subapp_exposes_project_listing(api_client: TestClient, tmp_path: Path) -> None:
    project_path = tmp_path / "workspace-project"
    project_path.mkdir(parents=True)

    register_response = api_client.post(
        "/api/projects/register",
        json={"project_path": str(project_path)},
    )
    assert register_response.status_code == 200

    response = api_client.get("/workspace/api/projects")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert any(project["project_path"] == str(project_path) for project in payload)
