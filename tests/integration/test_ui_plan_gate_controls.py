import json
import os
import subprocess
import tempfile
from pathlib import Path


ROUTE_STATE_STORAGE_KEY = "sparkspawn.ui_route_state"


def _run_store_probe(initial_route_state: dict[str, object], actions: list[dict[str, object]]) -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[2]
    frontend_dir = repo_root / "frontend"

    with tempfile.TemporaryDirectory(prefix=".tmp-store-probe-", dir=frontend_dir) as temp_dir:
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
                str(frontend_dir / "src" / "store.ts"),
            ],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )

        probe_script = """
import { pathToFileURL } from 'node:url'

const routeKey = process.env.ROUTE_KEY
const routeState = JSON.parse(process.env.INIT_ROUTE_STATE)
const actions = JSON.parse(process.env.ACTIONS)
const storage = new Map()
const localStorage = {
  getItem: (key) => (storage.has(key) ? storage.get(key) : null),
  setItem: (key, value) => { storage.set(key, String(value)) },
  removeItem: (key) => { storage.delete(key) },
}
globalThis.window = { localStorage }
window.localStorage.setItem(routeKey, JSON.stringify(routeState))

const mod = await import(pathToFileURL(process.env.STORE_JS_PATH).href)
const snapshots = []
const record = (label) => {
  const state = mod.useStore.getState()
  snapshots.push({
    label,
    activeProjectPath: state.activeProjectPath,
    activePlanId: state.activeProjectPath
      ? state.projectScopedWorkspaces[state.activeProjectPath]?.planId ?? null
      : null,
    activePlanStatus: state.activeProjectPath
      ? state.projectScopedWorkspaces[state.activeProjectPath]?.planStatus ?? null
      : null,
    projectScopedWorkspaces: state.projectScopedWorkspaces,
  })
}

record('initial')
for (const action of actions) {
  const state = mod.useStore.getState()
  if (action.type === 'setActiveProjectPath') state.setActiveProjectPath(action.value)
  if (action.type === 'setPlanId') state.setPlanId(action.value)
  if (action.type === 'setPlanStatus') state.setPlanStatus(action.value)
  record(action.type)
}

console.log(JSON.stringify({ snapshots }))
""".strip()

        env = os.environ.copy()
        env.update(
            {
                "STORE_JS_PATH": str(out_dir / "store.js"),
                "INIT_ROUTE_STATE": json.dumps(initial_route_state),
                "ACTIONS": json.dumps(actions),
                "ROUTE_KEY": ROUTE_STATE_STORAGE_KEY,
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


def _run_store_reload_probe(initial_route_state: dict[str, object]) -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[2]
    frontend_dir = repo_root / "frontend"

    with tempfile.TemporaryDirectory(prefix=".tmp-store-probe-", dir=frontend_dir) as temp_dir:
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
                str(frontend_dir / "src" / "store.ts"),
            ],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )

        probe_script = """
import { pathToFileURL } from 'node:url'

const routeKey = process.env.ROUTE_KEY
const routeState = JSON.parse(process.env.INIT_ROUTE_STATE)
const storage = new Map()
const localStorage = {
  getItem: (key) => (storage.has(key) ? storage.get(key) : null),
  setItem: (key, value) => { storage.set(key, String(value)) },
  removeItem: (key) => { storage.delete(key) },
}
globalThis.window = { localStorage }
window.localStorage.setItem(routeKey, JSON.stringify(routeState))

const storeUrl = pathToFileURL(process.env.STORE_JS_PATH).href
const modFirst = await import(`${storeUrl}?session=first`)
const stateFirst = modFirst.useStore.getState()
stateFirst.setPlanId('plan-alpha')
stateFirst.setPlanStatus('approved')

const modSecond = await import(`${storeUrl}?session=second`)
const stateSecond = modSecond.useStore.getState()
const restoredScope = stateSecond.projectScopedWorkspaces['/tmp/project-alpha'] ?? null
console.log(JSON.stringify({
  planId: restoredScope?.planId ?? null,
  planStatus: restoredScope?.planStatus ?? null,
}))
""".strip()

        env = os.environ.copy()
        env.update(
            {
                "STORE_JS_PATH": str(out_dir / "store.js"),
                "INIT_ROUTE_STATE": json.dumps(initial_route_state),
                "ROUTE_KEY": ROUTE_STATE_STORAGE_KEY,
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


def test_projects_panel_exposes_plan_gate_controls_with_explicit_status_transitions_item_8_5_03() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    projects_panel_text = (repo_root / "frontend" / "src" / "components" / "ProjectsPanel.tsx").read_text(
        encoding="utf-8"
    )
    store_text = (repo_root / "frontend" / "src" / "store.ts").read_text(encoding="utf-8")

    store_snippets = [
        "type PlanStatus = 'draft' | 'approved' | 'rejected' | 'revision-requested'",
        "planStatus: PlanStatus",
        "setPlanStatus: (status: PlanStatus) => void",
        "planStatus: 'draft',",
    ]
    for snippet in store_snippets:
        assert snippet in store_text, f"missing plan status state snippet: {snippet}"

    required_projects_panel_snippets = [
        "const PLAN_STATUS_TRANSITIONS: Record<PlanStatus, PlanStatus[]> = {",
        "const canTransitionPlanStatus = (from: PlanStatus, to: PlanStatus) =>",
        "const onPlanGateTransition = (nextStatus: PlanStatus) => {",
        "data-testid=\"project-plan-gate-surface\"",
        "data-testid=\"project-plan-approve-button\"",
        "data-testid=\"project-plan-reject-button\"",
        "data-testid=\"project-plan-request-revision-button\"",
        "Plan status:",
        "if (!activeProjectPath || !activeProjectScope?.planId) {",
        "if (!canTransitionPlanStatus(activeProjectScope.planStatus, nextStatus)) {",
    ]
    for snippet in required_projects_panel_snippets:
        assert snippet in projects_panel_text, f"missing plan gate control snippet: {snippet}"


def test_projects_panel_blocks_noop_plan_gate_transitions_item_8_5_03() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    projects_panel_text = (repo_root / "frontend" / "src" / "components" / "ProjectsPanel.tsx").read_text(
        encoding="utf-8"
    )

    assert "from !== to && PLAN_STATUS_TRANSITIONS[from].includes(to)" in projects_panel_text, (
        "plan gate transitions should reject no-op actions so only real status changes are enabled"
    )


def test_store_keeps_project_scoped_plan_gate_transitions_item_8_5_03() -> None:
    probe = _run_store_probe(
        initial_route_state={
            "viewMode": "projects",
            "activeProjectPath": "/tmp/project-alpha",
            "activeFlow": None,
            "selectedRunId": None,
        },
        actions=[
            {"type": "setPlanId", "value": "plan-alpha"},
            {"type": "setPlanStatus", "value": "approved"},
            {"type": "setPlanStatus", "value": "revision-requested"},
            {"type": "setPlanStatus", "value": "rejected"},
            {"type": "setActiveProjectPath", "value": "/tmp/project-beta"},
            {"type": "setPlanId", "value": "plan-beta"},
            {"type": "setPlanStatus", "value": "approved"},
            {"type": "setActiveProjectPath", "value": "/tmp/project-alpha"},
        ],
    )

    restored_alpha = probe["snapshots"][-1]
    all_scopes = restored_alpha["projectScopedWorkspaces"]
    assert restored_alpha["activeProjectPath"] == "/tmp/project-alpha"
    assert restored_alpha["activePlanId"] == "plan-alpha"
    assert restored_alpha["activePlanStatus"] == "rejected"
    assert all_scopes["/tmp/project-beta"]["planId"] == "plan-beta"
    assert all_scopes["/tmp/project-beta"]["planStatus"] == "approved"


def test_store_restores_plan_status_after_reload_item_8_5_03() -> None:
    restored = _run_store_reload_probe(
        initial_route_state={
            "viewMode": "projects",
            "activeProjectPath": "/tmp/project-alpha",
            "activeFlow": None,
            "selectedRunId": None,
        }
    )

    assert restored["planId"] == "plan-alpha"
    assert restored["planStatus"] == "approved"
