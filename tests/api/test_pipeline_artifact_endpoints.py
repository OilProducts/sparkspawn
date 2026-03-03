from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import attractor.api.server as server


def _seed_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, run_id: str) -> Path:
    runs_root = tmp_path / "runs"
    monkeypatch.setattr(server, "RUNS_ROOT", runs_root)

    server._write_run_meta(
        server.RunRecord(
            run_id=run_id,
            flow_name="Flow",
            status="success",
            result="success",
            working_directory=str(tmp_path / "work"),
            model="test-model",
            started_at="2026-01-01T00:00:00Z",
            ended_at="2026-01-01T00:01:00Z",
        )
    )
    return runs_root / run_id


def test_list_pipeline_artifacts_returns_run_outputs_for_known_pipeline(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_id = "run-artifacts-list"
    run_root = _seed_run(monkeypatch, tmp_path, run_id)

    (run_root / "manifest.json").write_text("{}", encoding="utf-8")
    (run_root / "checkpoint.json").write_text("{}", encoding="utf-8")

    stage_dir = run_root / "plan"
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / "prompt.md").write_text("# prompt", encoding="utf-8")
    (stage_dir / "response.md").write_text("# response", encoding="utf-8")
    (stage_dir / "status.json").write_text('{"outcome":"success"}', encoding="utf-8")

    artifact_file = run_root / "artifacts" / "logs" / "output.txt"
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_text("done", encoding="utf-8")

    # Internal checkpoint state should not be exposed by the artifact browser list.
    (run_root / "state.json").write_text("{}", encoding="utf-8")

    response = api_client.get(f"/pipelines/{run_id}/artifacts")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pipeline_id"] == run_id
    paths = [item["path"] for item in payload["artifacts"]]
    assert paths == [
        "artifacts/logs/output.txt",
        "checkpoint.json",
        "manifest.json",
        "plan/prompt.md",
        "plan/response.md",
        "plan/status.json",
    ]
    assert "state.json" not in paths


def test_get_pipeline_artifact_file_returns_file_for_known_artifact(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_id = "run-artifacts-file"
    run_root = _seed_run(monkeypatch, tmp_path, run_id)

    artifact_path = run_root / "plan" / "prompt.md"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("# prompt", encoding="utf-8")

    response = api_client.get(f"/pipelines/{run_id}/artifacts/plan/prompt.md")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.text == "# prompt"


def test_get_pipeline_artifact_file_rejects_parent_traversal(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_id = "run-artifacts-traversal"
    _seed_run(monkeypatch, tmp_path, run_id)

    response = api_client.get(f"/pipelines/{run_id}/artifacts/%2E%2E/run.json")

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid artifact path"


def test_get_pipeline_artifact_file_returns_404_when_missing(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_id = "run-artifacts-missing"
    _seed_run(monkeypatch, tmp_path, run_id)

    response = api_client.get(f"/pipelines/{run_id}/artifacts/plan/missing.md")

    assert response.status_code == 404
    assert response.json()["detail"] == "Artifact not found"
