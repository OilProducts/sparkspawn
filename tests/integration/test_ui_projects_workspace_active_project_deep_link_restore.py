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
    viewMode: state.viewMode,
    activeProjectPath: state.activeProjectPath,
    activeFlow: state.activeFlow,
    selectedRunId: state.selectedRunId,
    workingDir: state.workingDir,
    projectScope: state.activeProjectPath ? state.projectScopedWorkspaces[state.activeProjectPath] : null,
  })
}

record('initial')
for (const action of actions) {
  const state = mod.useStore.getState()
  if (action.type === 'setActiveProjectPath') {
    state.setActiveProjectPath(action.value)
  }
  record(action.type)
}

console.log(JSON.stringify({
  snapshots,
  persistedRouteState: JSON.parse(window.localStorage.getItem(routeKey)),
}))
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


def test_store_restores_active_project_identity_from_deep_link_state_item_4_3_07() -> None:
    probe = _run_store_probe(
        initial_route_state={
            "viewMode": "editor",
            "activeProjectPath": "/tmp/project-alpha",
            "activeFlow": "flow-alpha",
            "selectedRunId": "run-alpha",
        },
        actions=[],
    )

    initial = probe["snapshots"][0]
    assert initial["viewMode"] == "editor"
    assert initial["activeProjectPath"] == "/tmp/project-alpha"
    assert initial["activeFlow"] == "flow-alpha"
    assert initial["selectedRunId"] == "run-alpha"
    assert initial["projectScope"]["activeFlow"] == "flow-alpha"
    assert initial["projectScope"]["selectedRunId"] == "run-alpha"


def test_store_persists_active_project_identity_round_trip_item_4_3_07() -> None:
    probe = _run_store_probe(
        initial_route_state={
            "viewMode": "editor",
            "activeProjectPath": "/tmp/project-alpha",
            "activeFlow": "flow-alpha",
            "selectedRunId": "run-alpha",
        },
        actions=[{"type": "setActiveProjectPath", "value": "/tmp/project-beta"}],
    )

    switched = probe["snapshots"][-1]
    assert switched["viewMode"] == "editor"
    assert switched["activeProjectPath"] == "/tmp/project-beta"
    assert switched["activeFlow"] is None
    assert switched["selectedRunId"] is None

    persisted = probe["persistedRouteState"]
    assert persisted["viewMode"] == "editor"
    assert persisted["activeProjectPath"] == "/tmp/project-beta"
    assert persisted["activeFlow"] is None
    assert persisted["selectedRunId"] is None


def test_store_downgrades_view_mode_when_active_project_cleared_item_4_3_07() -> None:
    probe = _run_store_probe(
        initial_route_state={
            "viewMode": "editor",
            "activeProjectPath": "/tmp/project-alpha",
            "activeFlow": "flow-alpha",
            "selectedRunId": "run-alpha",
        },
        actions=[{"type": "setActiveProjectPath", "value": None}],
    )

    cleared = probe["snapshots"][-1]
    assert cleared["viewMode"] == "projects"
    assert cleared["activeProjectPath"] is None
    assert cleared["activeFlow"] is None
    assert cleared["selectedRunId"] is None

    persisted = probe["persistedRouteState"]
    assert persisted["viewMode"] == "projects"
    assert persisted["activeProjectPath"] is None
    assert persisted["activeFlow"] is None
    assert persisted["selectedRunId"] is None


