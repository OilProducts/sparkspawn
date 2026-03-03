from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


def _run_run_scope_probe() -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[2]
    frontend_dir = repo_root / "frontend"

    with tempfile.TemporaryDirectory(prefix=".tmp-run-scope-probe-", dir=frontend_dir) as temp_dir:
        out_dir = Path(temp_dir) / "compiled"
        out_dir.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            [
                "npm",
                "--prefix",
                str(frontend_dir),
                "exec",
                "--",
                "tsc",
                "--pretty",
                "false",
                "--target",
                "ES2022",
                "--module",
                "ESNext",
                "--moduleResolution",
                "bundler",
                "--skipLibCheck",
                "--outDir",
                str(out_dir),
                str(frontend_dir / "src" / "lib" / "runScope.ts"),
            ],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )

        probe_script = """
import { pathToFileURL } from 'node:url'

const mod = await import(pathToFileURL(process.env.RUN_SCOPE_JS_PATH).href)

const outOfScopeStatus = mod.resolveStatusHydrationDecision({
  selectedRunId: null,
  statusRunId: 'run-beta',
  statusRunWorkingDirectory: '/tmp/project-beta',
  activeProjectPath: '/tmp/project-alpha',
  statusRuntimeStatus: 'running',
})

const inScopeStatus = mod.resolveStatusHydrationDecision({
  selectedRunId: null,
  statusRunId: 'run-alpha',
  statusRunWorkingDirectory: '/tmp/project-alpha/build',
  activeProjectPath: '/tmp/project-alpha',
  statusRuntimeStatus: 'running',
})

const selectedRunMismatchStatus = mod.resolveStatusHydrationDecision({
  selectedRunId: 'run-alpha',
  statusRunId: 'run-beta',
  statusRunWorkingDirectory: '/tmp/project-beta',
  activeProjectPath: '/tmp/project-alpha',
  statusRuntimeStatus: 'failed',
})

const outOfScopePreflight = mod.resolveSelectedRunScopePreflight({
  selectedRunWorkingDirectory: '/tmp/project-beta',
  activeProjectPath: '/tmp/project-alpha',
  selectedRunStatus: 'running',
})

const inScopePreflight = mod.resolveSelectedRunScopePreflight({
  selectedRunWorkingDirectory: '/tmp/project-alpha/work',
  activeProjectPath: '/tmp/project-alpha',
  selectedRunStatus: 'running',
})

console.log(JSON.stringify({
  outOfScopeStatus,
  inScopeStatus,
  selectedRunMismatchStatus,
  outOfScopePreflight,
  inScopePreflight,
}))
""".strip()

        env = os.environ.copy()
        env.update(
            {
                "RUN_SCOPE_JS_PATH": str(out_dir / "runScope.js"),
            }
        )

        result = subprocess.run(
            ["node", "--input-type=module", "-e", probe_script],
            cwd=frontend_dir,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        return json.loads(result.stdout)


def test_status_hydration_decisions_prevent_cross_project_run_leakage_item_4_2_05() -> None:
    probe = _run_run_scope_probe()

    assert probe["outOfScopeStatus"] == {
        "nextSelectedRunId": None,
        "nextRuntimeStatus": "idle",
    }
    assert probe["inScopeStatus"] == {
        "nextSelectedRunId": "run-alpha",
        "nextRuntimeStatus": "running",
    }
    assert probe["selectedRunMismatchStatus"] == {
        "nextSelectedRunId": None,
        "nextRuntimeStatus": None,
    }


def test_selected_run_preflight_blocks_out_of_scope_stream_item_4_2_05() -> None:
    probe = _run_run_scope_probe()

    assert probe["outOfScopePreflight"] == {
        "allowStream": False,
        "clearSelectedRun": True,
        "nextRuntimeStatus": "idle",
    }
    assert probe["inScopePreflight"] == {
        "allowStream": True,
        "clearSelectedRun": False,
        "nextRuntimeStatus": "running",
    }
