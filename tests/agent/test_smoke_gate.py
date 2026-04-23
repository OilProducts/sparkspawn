from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OPT_IN_SKIP_REASON = (
    "live smoke tests are opt-in; use --live-smoke, -m live_smoke, "
    "-k live_smoke, or select tests/agent/test_live_smoke.py directly"
)
MISSING_CREDENTIALS_REASON = (
    "missing live smoke credentials: OPENAI_API_KEY, ANTHROPIC_API_KEY, "
    "GEMINI_API_KEY or GOOGLE_API_KEY"
)


def _child_pytest_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in ("PYTEST_ADDOPTS", "PYTEST_CURRENT_TEST"):
        env.pop(name, None)
    return env


def _run_pytest(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    uv = shutil.which("uv")
    assert uv is not None

    return subprocess.run(
        [uv, "run", "pytest", *args],
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
        env=env or _child_pytest_env(),
        text=True,
    )


def test_default_pytest_selection_keeps_live_smoke_opt_in() -> None:
    result = _run_pytest("-q", "-rs", "tests/agent", "-k", "selection_probe")
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert OPT_IN_SKIP_REASON in output
    assert "tests/agent/test_live_smoke.py" in output


def test_explicit_live_smoke_selection_requires_credentials() -> None:
    env = _child_pytest_env()
    for name in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
    ):
        env.pop(name, None)

    result = _run_pytest(
        "-q",
        "-rs",
        "tests/agent",
        "-k",
        "selection_probe",
        "--live-smoke",
        env=env,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert MISSING_CREDENTIALS_REASON in output
    assert "tests/agent/test_live_smoke.py" in output
