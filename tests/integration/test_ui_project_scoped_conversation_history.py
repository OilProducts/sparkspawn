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
    activeProjectConversationId: state.activeProjectPath
      ? state.projectScopedWorkspaces[state.activeProjectPath]?.conversationId ?? null
      : null,
    activeProjectConversationHistory: state.activeProjectPath
      ? state.projectScopedWorkspaces[state.activeProjectPath]?.conversationHistory ?? []
      : [],
    projectScopedWorkspaces: state.projectScopedWorkspaces,
  })
}

record('initial')
for (const action of actions) {
  const state = mod.useStore.getState()
  if (action.type === 'setActiveProjectPath') state.setActiveProjectPath(action.value)
  if (action.type === 'setConversationId') state.setConversationId(action.value)
  if (action.type === 'appendConversationHistoryEntry') state.appendConversationHistoryEntry(action.value)
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
stateFirst.setConversationId('conversation-alpha')
stateFirst.appendConversationHistoryEntry({
  role: 'user',
  content: 'Persist this across reload',
  timestamp: '2026-03-01T00:05:00Z',
})

const modSecond = await import(`${storeUrl}?session=second`)
const stateSecond = modSecond.useStore.getState()
const restoredScope = stateSecond.projectScopedWorkspaces['/tmp/project-alpha'] ?? null
console.log(JSON.stringify({
  conversationId: restoredScope?.conversationId ?? null,
  conversationHistory: restoredScope?.conversationHistory ?? [],
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


def test_store_persists_project_scoped_conversation_history_item_5_5_02() -> None:
    probe = _run_store_probe(
        initial_route_state={
            "viewMode": "projects",
            "activeProjectPath": "/tmp/project-alpha",
            "activeFlow": None,
            "selectedRunId": None,
        },
        actions=[
            {"type": "setConversationId", "value": "conversation-alpha"},
            {
                "type": "appendConversationHistoryEntry",
                "value": {
                    "role": "user",
                    "content": "Define alpha spec scope",
                    "timestamp": "2026-03-01T00:00:00Z",
                },
            },
            {
                "type": "appendConversationHistoryEntry",
                "value": {
                    "role": "assistant",
                    "content": "Drafted alpha acceptance criteria",
                    "timestamp": "2026-03-01T00:01:00Z",
                },
            },
            {"type": "setActiveProjectPath", "value": "/tmp/project-beta"},
            {"type": "setConversationId", "value": "conversation-beta"},
            {
                "type": "appendConversationHistoryEntry",
                "value": {
                    "role": "user",
                    "content": "Define beta rollout plan",
                    "timestamp": "2026-03-01T00:02:00Z",
                },
            },
            {"type": "setActiveProjectPath", "value": "/tmp/project-alpha"},
        ],
    )

    alpha_restored = probe["snapshots"][-1]
    assert alpha_restored["activeProjectPath"] == "/tmp/project-alpha"
    assert alpha_restored["activeProjectConversationId"] == "conversation-alpha"
    assert alpha_restored["activeProjectConversationHistory"] == [
        {
            "role": "user",
            "content": "Define alpha spec scope",
            "timestamp": "2026-03-01T00:00:00Z",
        },
        {
            "role": "assistant",
            "content": "Drafted alpha acceptance criteria",
            "timestamp": "2026-03-01T00:01:00Z",
        },
    ]

    all_scopes = alpha_restored["projectScopedWorkspaces"]
    assert all_scopes["/tmp/project-beta"]["conversationId"] == "conversation-beta"
    assert all_scopes["/tmp/project-beta"]["conversationHistory"] == [
        {
            "role": "user",
            "content": "Define beta rollout plan",
            "timestamp": "2026-03-01T00:02:00Z",
        }
    ]


def test_store_restores_project_scoped_conversation_history_after_reload_item_5_5_02() -> None:
    restored = _run_store_reload_probe(
        initial_route_state={
            "viewMode": "projects",
            "activeProjectPath": "/tmp/project-alpha",
            "activeFlow": None,
            "selectedRunId": None,
        }
    )

    assert restored["conversationId"] == "conversation-alpha"
    assert restored["conversationHistory"] == [
        {
            "role": "user",
            "content": "Persist this across reload",
            "timestamp": "2026-03-01T00:05:00Z",
        }
    ]


def test_projects_panel_renders_project_scoped_conversation_history_item_5_5_02() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    projects_panel_text = (repo_root / "frontend" / "src" / "components" / "ProjectsPanel.tsx").read_text(encoding="utf-8")

    required_snippets = [
        'data-testid="project-ai-conversation-history"',
        "Conversation history",
        "Conversation history is scoped to the active project and remains discoverable when you return.",
        "No conversation history for this project yet.",
    ]

    for snippet in required_snippets:
        assert snippet in projects_panel_text, f"missing project-scoped conversation history snippet: {snippet}"


