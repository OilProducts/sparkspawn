from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import attractor.api.server as server


def test_project_metadata_returns_name_directory_and_branch_for_git_repo(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_dir = tmp_path / "demo-project"
    project_dir.mkdir()

    branch_cmd = ["git", "-C", str(project_dir), "rev-parse", "--abbrev-ref", "HEAD"]
    commit_cmd = ["git", "-C", str(project_dir), "rev-parse", "HEAD"]

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool) -> subprocess.CompletedProcess[str]:
        assert cmd == branch_cmd or cmd == commit_cmd
        assert capture_output is True
        assert text is True
        assert check is True
        if cmd == branch_cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="feature/ui-metadata\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="abc123def456\n", stderr="")

    monkeypatch.setattr(server.subprocess, "run", fake_run)

    response = api_client.get(
        "/api/projects/metadata",
        params={"directory": str(project_dir)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "name": "demo-project",
        "directory": str(project_dir),
        "branch": "feature/ui-metadata",
        "commit": "abc123def456",
    }


def test_project_metadata_returns_null_branch_for_non_git_directory(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_dir = tmp_path / "non-git-project"
    project_dir.mkdir()

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(returncode=128, cmd=cmd, stderr="not a git repository")

    monkeypatch.setattr(server.subprocess, "run", fake_run)

    response = api_client.get(
        "/api/projects/metadata",
        params={"directory": str(project_dir)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "name": "non-git-project",
        "directory": str(project_dir),
        "branch": None,
        "commit": None,
    }


def test_project_metadata_rejects_non_absolute_directory(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/projects/metadata",
        params={"directory": "./relative-project"},
    )

    assert response.status_code == 400
    assert "must be absolute" in response.json()["detail"]
