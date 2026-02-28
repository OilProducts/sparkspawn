from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest
from fastapi import HTTPException

import attractor.api.server as server


def test_project_metadata_returns_name_directory_and_branch_for_git_repo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_dir = tmp_path / "demo-project"
    project_dir.mkdir()

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool) -> subprocess.CompletedProcess[str]:
        assert cmd == ["git", "-C", str(project_dir), "rev-parse", "--abbrev-ref", "HEAD"]
        assert capture_output is True
        assert text is True
        assert check is True
        return subprocess.CompletedProcess(cmd, 0, stdout="feature/ui-metadata\n", stderr="")

    monkeypatch.setattr(server.subprocess, "run", fake_run)

    payload = asyncio.run(server.get_project_metadata(str(project_dir)))

    assert payload == {
        "name": "demo-project",
        "directory": str(project_dir),
        "branch": "feature/ui-metadata",
    }


def test_project_metadata_returns_null_branch_for_non_git_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_dir = tmp_path / "non-git-project"
    project_dir.mkdir()

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(returncode=128, cmd=cmd, stderr="not a git repository")

    monkeypatch.setattr(server.subprocess, "run", fake_run)

    payload = asyncio.run(server.get_project_metadata(str(project_dir)))

    assert payload == {
        "name": "non-git-project",
        "directory": str(project_dir),
        "branch": None,
    }


def test_project_metadata_rejects_non_absolute_directory() -> None:
    with pytest.raises(HTTPException, match="must be absolute") as exc:
        asyncio.run(server.get_project_metadata("./relative-project"))

    assert exc.value.status_code == 400
