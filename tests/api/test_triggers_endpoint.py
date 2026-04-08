from __future__ import annotations

from pathlib import Path
import time

import pytest
from fastapi.testclient import TestClient

import attractor.api.server as server
from tests.support.flow_fixtures import seed_flow_fixture

TEST_PLANNING_FLOW = "test-planning.dot"


def _seed_flow(name: str) -> None:
    seed_flow_fixture(server.get_settings().flows_dir, "minimal-valid.dot", as_name=name)


def test_create_and_list_custom_schedule_trigger(
    product_api_client: TestClient,
    tmp_path: Path,
) -> None:
    project_dir = (tmp_path / "schedule-project").resolve()
    project_dir.mkdir()
    _seed_flow(TEST_PLANNING_FLOW)

    create_response = product_api_client.post(
        "/workspace/api/triggers",
        json={
            "name": "Daily planning",
            "enabled": True,
            "source_type": "schedule",
            "action": {
                "flow_name": TEST_PLANNING_FLOW,
                "project_path": str(project_dir),
                "static_context": {"origin": "test"},
            },
            "source": {
                "kind": "interval",
                "interval_seconds": 300,
            },
        },
    )

    assert create_response.status_code == 200
    created_payload = create_response.json()
    assert created_payload["name"] == "Daily planning"
    assert created_payload["source_type"] == "schedule"
    assert created_payload["action"]["flow_name"] == TEST_PLANNING_FLOW
    assert created_payload["action"]["project_path"] == str(project_dir)
    assert created_payload["state"]["next_run_at"]

    list_response = product_api_client.get("/workspace/api/triggers")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert [entry["id"] for entry in listed] == [created_payload["id"]]


def test_webhook_trigger_accepts_valid_secret_and_launches_flow(
    product_api_client: TestClient,
    tmp_path: Path,
) -> None:
    project_dir = (tmp_path / "webhook-project").resolve()
    project_dir.mkdir()
    _seed_flow("webhook.dot")

    create_response = product_api_client.post(
        "/workspace/api/triggers",
        json={
            "name": "Webhook launch",
            "enabled": True,
            "source_type": "webhook",
            "action": {
                "flow_name": "webhook.dot",
                "project_path": str(project_dir),
                "static_context": {"source": "webhook-test"},
            },
            "source": {},
        },
    )

    assert create_response.status_code == 200
    trigger_payload = create_response.json()
    webhook_key = trigger_payload["source"]["webhook_key"]
    webhook_secret = trigger_payload["webhook_secret"]

    bad_secret_response = product_api_client.post(
        "/workspace/api/webhooks",
        headers={
            "X-Spark-Webhook-Key": webhook_key,
            "X-Spark-Webhook-Secret": "wrong-secret",
        },
        json={"value": 1},
    )
    assert bad_secret_response.status_code == 403

    webhook_response = product_api_client.post(
        "/workspace/api/webhooks",
        headers={
            "X-Spark-Webhook-Key": webhook_key,
            "X-Spark-Webhook-Secret": webhook_secret,
            "X-Spark-Webhook-Request-Id": "request-1",
        },
        json={"value": 1},
    )
    assert webhook_response.status_code == 200
    assert webhook_response.json()["trigger_id"] == trigger_payload["id"]

    deadline = time.time() + 5.0
    while time.time() < deadline:
        runs_response = product_api_client.get("/attractor/runs", params={"project_path": str(project_dir)})
        assert runs_response.status_code == 200
        run_ids = [run["run_id"] for run in runs_response.json()["runs"] if run["flow_name"] == "webhook.dot"]
        if run_ids:
            break
        time.sleep(0.1)
    else:
        pytest.fail("Timed out waiting for webhook trigger run.")
