from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

import attractor.api.server as server


ADVANCED_NODE_ATTR_KEYS = (
    "max_retries",
    "goal_gate",
    "retry_target",
    "fallback_retry_target",
    "fidelity",
    "thread_id",
    "class",
    "timeout",
    "llm_model",
    "llm_provider",
    "reasoning_effort",
    "auto_status",
    "allow_partial",
    "human.default_choice",
)


def _generate_dot_with_advanced_node_attrs() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    frontend_dir = repo_root / "frontend"

    with tempfile.TemporaryDirectory(prefix=".tmp-dotutils-node-advanced-", dir=frontend_dir) as temp_dir:
        temp_path = Path(temp_dir)
        out_dir = temp_path / "out"
        out_dir.mkdir(parents=True, exist_ok=True)

        probe_tsconfig = temp_path / "tsconfig.json"
        probe_tsconfig.write_text(
            """{
  "extends": "../tsconfig.app.json",
  "compilerOptions": {
    "noEmit": false,
    "noEmitOnError": false,
    "allowImportingTsExtensions": false,
    "outDir": "./out"
  },
  "include": ["../src/lib/dotUtils.ts"]
}
""",
            encoding="utf-8",
        )

        compile_result = subprocess.run(
            [
                "npm",
                "--prefix",
                str(frontend_dir),
                "exec",
                "--",
                "tsc",
                "--pretty",
                "false",
                "--project",
                str(probe_tsconfig),
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        dot_utils_js = out_dir / "lib" / "dotUtils.js"
        if not dot_utils_js.exists():
            raise AssertionError(
                "Failed to compile dotUtils.ts for node-advanced-attrs probe.\n"
                f"stdout:\n{compile_result.stdout}\n"
                f"stderr:\n{compile_result.stderr}"
            )

        probe_script = """
import { pathToFileURL } from 'node:url'
const mod = await import(pathToFileURL(process.env.DOT_UTILS_JS_PATH).href)
const nodes = [
  { id: 'start', data: { label: 'Start', shape: 'Mdiamond' } },
  {
    id: 'task',
    data: {
      label: 'Task',
      shape: 'box',
      prompt: 'Do work',
      max_retries: '2',
      goal_gate: true,
      retry_target: 'fix',
      fallback_retry_target: 'done',
      fidelity: 'summary:low',
      thread_id: 'thread-a',
      class: 'critical',
      timeout: '900s',
      llm_model: 'gpt-5',
      llm_provider: 'openai',
      reasoning_effort: 'high',
      auto_status: true,
      allow_partial: true
    }
  },
  {
    id: 'gate',
    data: {
      label: 'Gate',
      shape: 'hexagon',
      prompt: 'Choose path',
      'human.default_choice': 'fix'
    }
  },
  { id: 'fix', data: { label: 'Fix', shape: 'box', prompt: 'Fix issue' } },
  { id: 'done', data: { label: 'Done', shape: 'Msquare' } }
]
const edges = [
  { id: 'e1', source: 'start', target: 'task' },
  { id: 'e2', source: 'task', target: 'gate' },
  { id: 'e3', source: 'gate', target: 'fix', data: { label: 'Fix' } },
  { id: 'e4', source: 'gate', target: 'done', data: { label: 'Ship' } },
  { id: 'e5', source: 'fix', target: 'done' }
]
const dot = mod.generateDot('node_advanced_attrs_probe', nodes, edges, {})
console.log(dot)
""".strip()

        env = os.environ.copy()
        env["DOT_UTILS_JS_PATH"] = str(dot_utils_js)
        probe_result = subprocess.run(
            ["node", "--input-type=module", "-e", probe_script],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        return probe_result.stdout


def test_node_advanced_attr_controls_present_item_6_2_02() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    sidebar_text = (repo_root / "frontend" / "src" / "components" / "Sidebar.tsx").read_text(encoding="utf-8")
    task_node_text = (repo_root / "frontend" / "src" / "components" / "TaskNode.tsx").read_text(encoding="utf-8")

    assert "Max Retries" in sidebar_text
    assert "Goal Gate" in sidebar_text
    assert "Retry Target" in sidebar_text
    assert "Fallback Retry Target" in sidebar_text
    assert "Fidelity" in sidebar_text
    assert "Thread ID" in sidebar_text
    assert "Class" in sidebar_text
    assert "Timeout" in sidebar_text
    assert "LLM Model" in sidebar_text
    assert "LLM Provider" in sidebar_text
    assert "Reasoning Effort" in sidebar_text
    assert "Auto Status" in sidebar_text
    assert "Allow Partial" in sidebar_text
    assert "Human Default Choice" in sidebar_text

    assert "Max Retries" in task_node_text
    assert "Goal Gate" in task_node_text
    assert "Retry Target" in task_node_text
    assert "Fallback Retry Target" in task_node_text
    assert "Fidelity" in task_node_text
    assert "Thread ID" in task_node_text
    assert "Class" in task_node_text
    assert "Timeout" in task_node_text
    assert "LLM Model" in task_node_text
    assert "LLM Provider" in task_node_text
    assert "Reasoning Effort" in task_node_text
    assert "Auto Status" in task_node_text
    assert "Allow Partial" in task_node_text
    assert "Human Default Choice" in task_node_text


def test_node_advanced_attrs_round_trip_through_preview_item_6_2_02() -> None:
    flow = _generate_dot_with_advanced_node_attrs()
    payload = asyncio.run(server.preview_pipeline(server.PreviewRequest(flow_content=flow)))
    nodes = payload["graph"]["nodes"]

    task_node = next((node for node in nodes if node["id"] == "task"), None)
    gate_node = next((node for node in nodes if node["id"] == "gate"), None)

    assert task_node is not None
    assert gate_node is not None

    assert task_node["max_retries"] == 2
    assert task_node["goal_gate"] is True
    assert task_node["retry_target"] == "fix"
    assert task_node["fallback_retry_target"] == "done"
    assert task_node["fidelity"] == "summary:low"
    assert task_node["thread_id"] == "thread-a"
    assert task_node["class"] == "critical"
    assert task_node["timeout"] == "900s"
    assert task_node["llm_model"] == "gpt-5"
    assert task_node["llm_provider"] == "openai"
    assert task_node["reasoning_effort"] == "high"
    assert task_node["auto_status"] is True
    assert task_node["allow_partial"] is True
    assert gate_node["human.default_choice"] == "fix"


