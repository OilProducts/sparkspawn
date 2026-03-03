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
    activeFlow: state.activeFlow,
    selectedRunId: state.selectedRunId,
    selectedNodeId: state.selectedNodeId,
    selectedEdgeId: state.selectedEdgeId,
    runtimeStatus: state.runtimeStatus,
    logs: state.logs,
    humanGate: state.humanGate,
    graphAttrs: state.graphAttrs,
    diagnostics: state.diagnostics,
    hasValidationErrors: state.hasValidationErrors,
    saveState: state.saveState,
    saveErrorMessage: state.saveErrorMessage,
    saveErrorKind: state.saveErrorKind,
    activeProjectConversationId: state.activeProjectPath
      ? state.projectScopedWorkspaces[state.activeProjectPath]?.conversationId ?? null
      : null,
    projectScopedWorkspaces: state.projectScopedWorkspaces,
  })
}

record('initial')
for (const action of actions) {
  const state = mod.useStore.getState()
  if (action.type === 'setActiveProjectPath') state.setActiveProjectPath(action.value)
  if (action.type === 'setConversationId') state.setConversationId(action.value)
  if (action.type === 'setGraphAttrs') state.setGraphAttrs(action.value)
  if (action.type === 'setDiagnostics') state.setDiagnostics(action.value)
  if (action.type === 'markSaveFailure') state.markSaveFailure(action.message, action.kind)
  if (action.type === 'setSelectedNodeId') state.setSelectedNodeId(action.value)
  if (action.type === 'setSelectedEdgeId') state.setSelectedEdgeId(action.value)
  if (action.type === 'setRuntimeStatus') state.setRuntimeStatus(action.value)
  if (action.type === 'addLog') state.addLog(action.value)
  if (action.type === 'setHumanGate') state.setHumanGate(action.value)
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


def test_store_project_switch_resets_flow_run_conversation_and_hidden_state_item_5_4_03() -> None:
    probe = _run_store_probe(
        initial_route_state={
            "viewMode": "editor",
            "activeProjectPath": "/tmp/project-alpha",
            "activeFlow": "flow-alpha",
            "selectedRunId": "run-alpha",
        },
        actions=[
            {"type": "setConversationId", "value": "conversation-alpha"},
            {"type": "setGraphAttrs", "value": {"goal": "alpha-goal"}},
            {
                "type": "setDiagnostics",
                "value": [{"rule_id": "E001", "severity": "error", "message": "diagnostic should clear on switch"}],
            },
            {"type": "markSaveFailure", "message": "save failed", "kind": "network"},
            {"type": "setSelectedNodeId", "value": "node-alpha"},
            {"type": "setSelectedEdgeId", "value": "edge-alpha"},
            {"type": "setRuntimeStatus", "value": "running"},
            {"type": "addLog", "value": {"time": "2026-02-28T00:00:00Z", "msg": "log", "type": "info"}},
            {
                "type": "setHumanGate",
                "value": {
                    "id": "gate-alpha",
                    "runId": "run-alpha",
                    "nodeId": "node-alpha",
                    "prompt": "continue?",
                    "options": [{"label": "Yes", "value": "yes"}],
                },
            },
            {"type": "setActiveProjectPath", "value": "/tmp/project-beta"},
            {"type": "setActiveProjectPath", "value": "/tmp/project-alpha"},
        ],
    )

    switched = probe["snapshots"][-2]
    assert switched["activeProjectPath"] == "/tmp/project-beta"
    assert switched["activeFlow"] is None
    assert switched["selectedRunId"] is None
    assert switched["activeProjectConversationId"] is None
    assert switched["selectedNodeId"] is None
    assert switched["selectedEdgeId"] is None
    assert switched["runtimeStatus"] == "idle"
    assert switched["logs"] == []
    assert switched["humanGate"] is None
    assert switched["graphAttrs"] == {}
    assert switched["diagnostics"] == []
    assert switched["hasValidationErrors"] is False
    assert switched["saveState"] == "idle"
    assert switched["saveErrorMessage"] is None
    assert switched["saveErrorKind"] is None
    assert switched["projectScopedWorkspaces"]["/tmp/project-alpha"]["conversationId"] == "conversation-alpha"

    restored = probe["snapshots"][-1]
    assert restored["activeProjectPath"] == "/tmp/project-alpha"
    assert restored["activeFlow"] == "flow-alpha"
    assert restored["selectedRunId"] == "run-alpha"
    assert restored["activeProjectConversationId"] == "conversation-alpha"


