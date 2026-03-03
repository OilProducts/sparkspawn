from __future__ import annotations

"""Cross-runtime frontend/backend DOT contract coverage.

This file consolidates UI DOT round-trip and advanced authoring contracts that
were previously split across multiple integration test modules.
"""


# ---- begin tests/integration/test_ui_edge_attributes_editor.py ----


import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

import attractor.api.server as server
from attractor.dsl import parse_dot
from attractor.engine.context import Context
from attractor.engine.executor import PipelineExecutor
from attractor.engine.outcome import Outcome, OutcomeStatus
from tests.contracts.frontend.frontend_behavior_runner import assert_frontend_behavior_test_passed


def _run_dot_utils_probe(probe_script: str, *, temp_prefix: str) -> str:
    repo_root = Path(__file__).resolve().parents[3]
    frontend_dir = repo_root / "frontend"

    with tempfile.TemporaryDirectory(prefix=temp_prefix, dir=frontend_dir) as temp_dir:
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
                "Failed to compile dotUtils.ts for edge-attrs probe.\n"
                f"stdout:\n{compile_result.stdout}\n"
                f"stderr:\n{compile_result.stderr}"
            )

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


def _generate_dot_with_edge_attrs() -> str:
    probe_script = """
import { pathToFileURL } from 'node:url'
const mod = await import(pathToFileURL(process.env.DOT_UTILS_JS_PATH).href)
const nodes = [
  { id: 'start', data: { label: 'Start', shape: 'Mdiamond' } },
  { id: 'route', data: { label: 'Route', shape: 'diamond', type: 'conditional', prompt: 'Route work' } },
  { id: 'done', data: { label: 'Done', shape: 'Msquare' } }
]
const edges = [
  {
    id: 'e1',
    source: 'start',
    target: 'route',
    data: {
      label: 'success',
      condition: 'outcome=success && context.tests_passed=true',
      weight: '7',
      fidelity: 'summary:low',
      thread_id: 'review-thread',
      loop_restart: true
    }
  },
  { id: 'e2', source: 'route', target: 'done' }
]
const dot = mod.generateDot('edge_attrs_probe', nodes, edges, {})
console.log(dot)
""".strip()
    return _run_dot_utils_probe(probe_script, temp_prefix=".tmp-dotutils-edge-attrs-")


def _generate_dot_with_edge_side_effect_attrs() -> str:
    probe_script = """
import { pathToFileURL } from 'node:url'
const mod = await import(pathToFileURL(process.env.DOT_UTILS_JS_PATH).href)
const nodes = [
  { id: 'start', data: { label: 'Start', shape: 'Mdiamond' } },
  { id: 'route', data: { label: 'Route', shape: 'diamond', type: 'conditional', prompt: 'Decide route' } },
  { id: 'work', data: { label: 'Work', shape: 'box', type: 'codergen', prompt: 'Do work' } },
  { id: 'done', data: { label: 'Done', shape: 'Msquare' } }
]
const edges = [
  { id: 'e1', source: 'start', target: 'route' },
  {
    id: 'e2',
    source: 'route',
    target: 'work',
    data: {
      label: 'restart-work',
      condition: 'outcome=success && context.tests_passed=true',
      weight: '5',
      fidelity: 'summary:low',
      thread_id: 'edge-thread',
      loop_restart: true
    }
  },
  {
    id: 'e3',
    source: 'route',
    target: 'done',
    data: {
      label: 'skip'
    }
  },
  { id: 'e4', source: 'work', target: 'done' }
]
const dot = mod.generateDot('edge_side_effect_probe', nodes, edges, { default_fidelity: 'full' })
console.log(dot)
""".strip()
    return _run_dot_utils_probe(probe_script, temp_prefix=".tmp-dotutils-edge-side-effects-")


def test_edge_editor_exposes_all_required_edge_attrs_item_6_3_01() -> None:
    assert_frontend_behavior_test_passed(
        "renders edge inspector controls and updates condition preview feedback from diagnostics"
    )


def test_edge_attrs_round_trip_through_preview_item_6_3_01() -> None:
    flow = _generate_dot_with_edge_attrs()
    payload = asyncio.run(server.preview_pipeline(server.PreviewRequest(flow_content=flow)))
    edges = payload["graph"]["edges"]

    edge = next((candidate for candidate in edges if candidate["from"] == "start" and candidate["to"] == "route"), None)
    assert edge is not None
    assert edge["label"] == "success"
    assert edge["condition"] == "outcome=success && context.tests_passed=true"
    assert edge["weight"] == 7
    assert edge["fidelity"] == "summary:low"
    assert edge["thread_id"] == "review-thread"
    assert edge["loop_restart"] is True


def test_edge_condition_field_exposes_syntax_hints_and_preview_feedback_item_6_3_02() -> None:
    assert_frontend_behavior_test_passed(
        "renders edge inspector controls and updates condition preview feedback from diagnostics"
    )


def test_edge_attr_serialization_and_execution_side_effect_visibility_item_6_3_03() -> None:
    flow = _generate_dot_with_edge_side_effect_attrs()
    payload = asyncio.run(server.preview_pipeline(server.PreviewRequest(flow_content=flow)))
    edges = payload["graph"]["edges"]

    edge = next((candidate for candidate in edges if candidate["from"] == "route" and candidate["to"] == "work"), None)
    assert edge is not None
    assert edge["label"] == "restart-work"
    assert edge["condition"] == "outcome=success && context.tests_passed=true"
    assert edge["weight"] == 5
    assert edge["fidelity"] == "summary:low"
    assert edge["thread_id"] == "edge-thread"
    assert edge["loop_restart"] is True

    graph = parse_dot(flow)
    seen_runtime_true: list[str] = []

    def runner(node_id: str, prompt: str, context: Context) -> Outcome:
        del prompt, context
        seen_runtime_true.append(node_id)
        return Outcome(status=OutcomeStatus.SUCCESS)

    result_true = PipelineExecutor(graph, runner).run(Context(values={"tests_passed": True}))

    assert result_true.status == "success"
    assert seen_runtime_true == ["start", "route", "work"]
    assert result_true.route_trace == ["work", "done"]
    assert result_true.completed_nodes == ["work"]

    seen_runtime_false: list[str] = []

    def runner_false(node_id: str, prompt: str, context: Context) -> Outcome:
        del prompt, context
        seen_runtime_false.append(node_id)
        return Outcome(status=OutcomeStatus.SUCCESS)

    result_false = PipelineExecutor(graph, runner_false).run(Context(values={"tests_passed": False}))

    assert result_false.status == "success"
    assert seen_runtime_false == ["start", "route"]
    assert result_false.route_trace == ["start", "route", "done"]
    assert result_false.completed_nodes == ["start", "route"]



# ---- end tests/integration/test_ui_edge_attributes_editor.py ----


# ---- begin tests/integration/test_ui_graph_attr_round_trip.py ----


import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path

import attractor.api.server as server


def _generate_dot_with_graph_attrs(graph_attrs: dict[str, object]) -> str:
    repo_root = Path(__file__).resolve().parents[3]
    frontend_dir = repo_root / "frontend"

    with tempfile.TemporaryDirectory(prefix=".tmp-dotutils-round-trip-", dir=frontend_dir) as temp_dir:
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
                "Failed to compile dotUtils.ts for round-trip probe.\n"
                f"stdout:\n{compile_result.stdout}\n"
                f"stderr:\n{compile_result.stderr}"
            )

        probe_script = """
import { pathToFileURL } from 'node:url'
const mod = await import(pathToFileURL(process.env.DOT_UTILS_JS_PATH).href)
const graphAttrs = JSON.parse(process.env.GRAPH_ATTRS_JSON)
const dot = mod.generateDot('round_trip_probe', [], [], graphAttrs)
console.log(dot)
""".strip()

        env = os.environ.copy()
        env.update(
            {
                "DOT_UTILS_JS_PATH": str(dot_utils_js),
                "GRAPH_ATTRS_JSON": json.dumps(graph_attrs),
            }
        )
        probe_result = subprocess.run(
            ["node", "--input-type=module", "-e", probe_script],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        return probe_result.stdout


def test_graph_attr_edit_round_trip_serializes_and_rehydrates_item_6_1_04() -> None:
    graph_attrs_input: dict[str, object] = {
        "goal": "Ship release",
        "label": "Release Graph",
        "model_stylesheet": ".fast { llm_model: fast-model; }",
        "default_max_retry": "3",
        "retry_target": "retry_stage",
        "fallback_retry_target": "fallback_stage",
        "default_fidelity": "summary:medium",
        "stack.child_dotfile": "child.dot",
        "stack.child_workdir": "/tmp/child",
        "tool_hooks.pre": "echo pre-hook",
        "tool_hooks.post": "echo post-hook",
    }
    flow = _generate_dot_with_graph_attrs(graph_attrs_input)
    payload = asyncio.run(server.preview_pipeline(server.PreviewRequest(flow_content=flow)))
    graph_attrs = payload["graph"]["graph_attrs"]

    assert graph_attrs["goal"] == "Ship release"
    assert graph_attrs["label"] == "Release Graph"
    assert graph_attrs["model_stylesheet"] == ".fast { llm_model: fast-model; }"
    assert graph_attrs["default_max_retry"] == 3
    assert graph_attrs["retry_target"] == "retry_stage"
    assert graph_attrs["fallback_retry_target"] == "fallback_stage"
    assert graph_attrs["default_fidelity"] == "summary:medium"
    assert graph_attrs["stack.child_dotfile"] == "child.dot"
    assert graph_attrs["stack.child_workdir"] == "/tmp/child"
    assert graph_attrs["tool_hooks.pre"] == "echo pre-hook"
    assert graph_attrs["tool_hooks.post"] == "echo post-hook"



# ---- end tests/integration/test_ui_graph_attr_round_trip.py ----


# ---- begin tests/integration/test_ui_node_advanced_attrs_editor.py ----


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
    repo_root = Path(__file__).resolve().parents[3]
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
    assert_frontend_behavior_test_passed(
        "renders advanced node controls for codergen and wait.human in sidebar inspector"
    )


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



# ---- end tests/integration/test_ui_node_advanced_attrs_editor.py ----


# ---- begin tests/integration/test_ui_node_handler_round_trip.py ----


import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path

import attractor.api.server as server


def _generate_dot_with_all_handler_types() -> str:
    repo_root = Path(__file__).resolve().parents[3]
    frontend_dir = repo_root / "frontend"

    nodes = [
        {"id": "start", "data": {"label": "Start", "shape": "Mdiamond", "type": "start"}},
        {
            "id": "code",
            "data": {
                "label": "Code",
                "shape": "box",
                "type": "codergen",
                "prompt": "Implement feature",
            },
        },
        {
            "id": "cond",
            "data": {
                "label": "Route",
                "shape": "diamond",
                "type": "conditional",
                "prompt": "Route based on result",
            },
        },
        {
            "id": "human",
            "data": {
                "label": "Review",
                "shape": "hexagon",
                "type": "wait.human",
                "prompt": "Approve release?",
                "human.default_choice": "approve",
            },
        },
        {
            "id": "tool",
            "data": {
                "label": "Tool",
                "shape": "parallelogram",
                "type": "tool",
                "tool_command": "echo run tool",
            },
        },
        {
            "id": "parallel",
            "data": {
                "label": "Parallel",
                "shape": "component",
                "type": "parallel",
                "join_policy": "wait_all",
                "error_policy": "continue",
                "max_parallel": "3",
            },
        },
        {
            "id": "fanin",
            "data": {
                "label": "Fan In",
                "shape": "tripleoctagon",
                "type": "parallel.fan_in",
                "prompt": "Merge branch outputs",
            },
        },
        {
            "id": "manager",
            "data": {
                "label": "Manager",
                "shape": "house",
                "type": "stack.manager_loop",
                "manager.poll_interval": "25ms",
                "manager.max_cycles": "3",
                "manager.stop_condition": 'child.status == "success"',
                "manager.actions": "observe,steer",
            },
        },
        {"id": "done", "data": {"label": "Done", "shape": "Msquare", "type": "exit"}},
    ]

    edges = [
        {"id": "e1", "source": "start", "target": "code"},
        {"id": "e2", "source": "code", "target": "cond"},
        {"id": "e3", "source": "cond", "target": "human", "data": {"label": "needs_approval"}},
        {"id": "e4", "source": "cond", "target": "tool", "data": {"label": "auto_path"}},
        {"id": "e5", "source": "human", "target": "parallel"},
        {"id": "e6", "source": "tool", "target": "parallel"},
        {"id": "e7", "source": "parallel", "target": "fanin"},
        {"id": "e8", "source": "fanin", "target": "manager"},
        {"id": "e9", "source": "manager", "target": "done"},
    ]

    with tempfile.TemporaryDirectory(prefix=".tmp-dotutils-node-handler-round-trip-", dir=frontend_dir) as temp_dir:
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
                "Failed to compile dotUtils.ts for node-handler-round-trip probe.\n"
                f"stdout:\n{compile_result.stdout}\n"
                f"stderr:\n{compile_result.stderr}"
            )

        probe_script = """
import { pathToFileURL } from 'node:url'
const mod = await import(pathToFileURL(process.env.DOT_UTILS_JS_PATH).href)
const nodes = JSON.parse(process.env.NODES_JSON)
const edges = JSON.parse(process.env.EDGES_JSON)
const dot = mod.generateDot('node_handler_round_trip_probe', nodes, edges, {})
console.log(dot)
""".strip()

        env = os.environ.copy()
        env.update(
            {
                "DOT_UTILS_JS_PATH": str(dot_utils_js),
                "NODES_JSON": json.dumps(nodes),
                "EDGES_JSON": json.dumps(edges),
            }
        )
        probe_result = subprocess.run(
            ["node", "--input-type=module", "-e", probe_script],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        return probe_result.stdout


def test_node_attributes_round_trip_across_all_handler_types_item_6_2_04() -> None:
    flow = _generate_dot_with_all_handler_types()
    payload = asyncio.run(server.preview_pipeline(server.PreviewRequest(flow_content=flow)))
    nodes = payload["graph"]["nodes"]
    nodes_by_id = {node["id"]: node for node in nodes}

    assert nodes_by_id["start"]["type"] == "start"
    assert nodes_by_id["code"]["type"] == "codergen"
    assert nodes_by_id["cond"]["type"] == "conditional"
    assert nodes_by_id["human"]["type"] == "wait.human"
    assert nodes_by_id["tool"]["type"] == "tool"
    assert nodes_by_id["parallel"]["type"] == "parallel"
    assert nodes_by_id["fanin"]["type"] == "parallel.fan_in"
    assert nodes_by_id["manager"]["type"] == "stack.manager_loop"
    assert nodes_by_id["done"]["type"] == "exit"

    assert nodes_by_id["code"]["prompt"] == "Implement feature"
    assert nodes_by_id["cond"]["prompt"] == "Route based on result"
    assert nodes_by_id["human"]["prompt"] == "Approve release?"
    assert nodes_by_id["human"]["human.default_choice"] == "approve"
    assert nodes_by_id["tool"]["tool_command"] == "echo run tool"
    assert nodes_by_id["parallel"]["join_policy"] == "wait_all"
    assert nodes_by_id["parallel"]["error_policy"] == "continue"
    assert nodes_by_id["parallel"]["max_parallel"] == 3
    assert nodes_by_id["fanin"]["prompt"] == "Merge branch outputs"
    assert nodes_by_id["manager"]["manager.poll_interval"] == "25ms"
    assert nodes_by_id["manager"]["manager.max_cycles"] == 3
    assert nodes_by_id["manager"]["manager.stop_condition"] == 'child.status == "success"'
    assert nodes_by_id["manager"]["manager.actions"] == "observe,steer"



# ---- end tests/integration/test_ui_node_handler_round_trip.py ----


# ---- begin tests/integration/test_ui_node_manager_loop_authoring.py ----


import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path

import attractor.api.server as server


def _generate_dot_with_manager_loop_attrs() -> str:
    repo_root = Path(__file__).resolve().parents[3]
    frontend_dir = repo_root / "frontend"

    with tempfile.TemporaryDirectory(prefix=".tmp-dotutils-manager-loop-", dir=frontend_dir) as temp_dir:
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
                "Failed to compile dotUtils.ts for manager-loop probe.\n"
                f"stdout:\n{compile_result.stdout}\n"
                f"stderr:\n{compile_result.stderr}"
            )

        probe_script = """
import { pathToFileURL } from 'node:url'
const mod = await import(pathToFileURL(process.env.DOT_UTILS_JS_PATH).href)
const nodes = [
  {
    id: 'manager',
    data: {
      label: 'Manager',
      shape: 'house',
      type: 'stack.manager_loop',
      'manager.poll_interval': '25ms',
      'manager.max_cycles': '3',
      'manager.stop_condition': 'child.status == "success"',
      'manager.actions': 'observe,steer'
    }
  }
]
const dot = mod.generateDot('manager_loop_probe', nodes, [], {})
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


def _generate_dot_from_preview_graph(graph_payload: dict[str, object]) -> str:
    repo_root = Path(__file__).resolve().parents[3]
    frontend_dir = repo_root / "frontend"

    with tempfile.TemporaryDirectory(prefix=".tmp-dotutils-manager-loop-roundtrip-", dir=frontend_dir) as temp_dir:
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
                "Failed to compile dotUtils.ts for manager-loop fixture round-trip probe.\n"
                f"stdout:\n{compile_result.stdout}\n"
                f"stderr:\n{compile_result.stderr}"
            )

        probe_script = """
import { pathToFileURL } from 'node:url'
const mod = await import(pathToFileURL(process.env.DOT_UTILS_JS_PATH).href)
const payload = JSON.parse(process.env.PREVIEW_GRAPH_JSON)
const nodes = payload.nodes.map((node) => {
  const { id, ...attrs } = node
  return { id, data: attrs }
})
const edges = payload.edges.map((edge) => {
  const { source, target, ...attrs } = edge
  return { source, target, data: attrs }
})
const dot = mod.generateDot('manager_loop_fixture_round_trip_probe', nodes, edges, payload.graph_attrs ?? {})
console.log(dot)
""".strip()

        env = os.environ.copy()
        env.update(
            {
                "DOT_UTILS_JS_PATH": str(dot_utils_js),
                "PREVIEW_GRAPH_JSON": json.dumps(graph_payload),
            }
        )
        probe_result = subprocess.run(
            ["node", "--input-type=module", "-e", probe_script],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        return probe_result.stdout


def test_manager_loop_authoring_controls_present_item_6_2_01() -> None:
    assert_frontend_behavior_test_passed(
        "renders manager-loop authoring controls and child-linkage affordance in sidebar inspector"
    )


def test_manager_loop_shape_and_type_are_selectable_item_6_7_01() -> None:
    assert_frontend_behavior_test_passed(
        "renders manager-loop shape and type options in task node toolbar"
    )


def test_manager_loop_control_fields_present_item_6_7_02() -> None:
    assert_frontend_behavior_test_passed(
        "renders manager-loop authoring controls and child-linkage affordance in sidebar inspector"
    )


def test_manager_loop_child_linkage_controls_present_item_6_7_03() -> None:
    assert_frontend_behavior_test_passed(
        "renders manager-loop authoring controls and child-linkage affordance in sidebar inspector"
    )



def test_manager_loop_attrs_round_trip_through_preview_item_6_2_01() -> None:
    flow = _generate_dot_with_manager_loop_attrs()
    payload = asyncio.run(server.preview_pipeline(server.PreviewRequest(flow_content=flow)))
    nodes = payload["graph"]["nodes"]
    manager_node = next((node for node in nodes if node["id"] == "manager"), None)

    assert manager_node is not None
    assert manager_node["shape"] == "house"
    assert manager_node["type"] == "stack.manager_loop"
    assert manager_node["manager.poll_interval"] == "25ms"
    assert manager_node["manager.max_cycles"] == 3
    assert manager_node["manager.stop_condition"] == 'child.status == "success"'
    assert manager_node["manager.actions"] == "observe,steer"


def test_manager_loop_fixture_round_trip_item_6_7_04() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    fixture_path = repo_root / "tests" / "fixtures" / "manager_loop_authoring_round_trip.dot"
    assert fixture_path.exists(), f"Missing manager-loop fixture: {fixture_path}"

    fixture_payload = asyncio.run(
        server.preview_pipeline(server.PreviewRequest(flow_content=fixture_path.read_text(encoding="utf-8")))
    )
    round_trip_flow = _generate_dot_from_preview_graph(fixture_payload["graph"])
    round_trip_payload = asyncio.run(server.preview_pipeline(server.PreviewRequest(flow_content=round_trip_flow)))

    fixture_graph_attrs = fixture_payload["graph"]["graph_attrs"]
    round_trip_graph_attrs = round_trip_payload["graph"]["graph_attrs"]
    assert round_trip_graph_attrs["stack.child_dotfile"] == fixture_graph_attrs["stack.child_dotfile"]
    assert round_trip_graph_attrs["stack.child_workdir"] == fixture_graph_attrs["stack.child_workdir"]

    fixture_manager = next(node for node in fixture_payload["graph"]["nodes"] if node["id"] == "manager")
    round_trip_manager = next(node for node in round_trip_payload["graph"]["nodes"] if node["id"] == "manager")
    for key in ("shape", "type", "manager.poll_interval", "manager.max_cycles", "manager.stop_condition", "manager.actions"):
        assert round_trip_manager[key] == fixture_manager[key]



# ---- end tests/integration/test_ui_node_manager_loop_authoring.py ----


# ---- begin tests/integration/test_ui_tool_hook_authoring.py ----


import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path

import attractor.api.server as server


def test_graph_settings_exposes_graph_scope_tool_hook_fields_item_6_6_01() -> None:
    assert_frontend_behavior_test_passed(
        "renders graph settings feedback for stylesheet diagnostics and tool hook warnings"
    )


def _generate_dot_with_node_tool_hook_overrides() -> str:
    repo_root = Path(__file__).resolve().parents[3]
    frontend_dir = repo_root / "frontend"

    with tempfile.TemporaryDirectory(prefix=".tmp-dotutils-node-tool-hooks-", dir=frontend_dir) as temp_dir:
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
                "Failed to compile dotUtils.ts for node-tool-hooks probe.\n"
                f"stdout:\n{compile_result.stdout}\n"
                f"stderr:\n{compile_result.stderr}"
            )

        probe_script = """
import { pathToFileURL } from 'node:url'
const mod = await import(pathToFileURL(process.env.DOT_UTILS_JS_PATH).href)
const nodes = [
  { id: 'start', data: { label: 'Start', shape: 'Mdiamond' } },
  {
    id: 'tool_node',
    data: {
      label: 'Tool',
      shape: 'parallelogram',
      type: 'tool',
      tool_command: 'echo run',
      'tool_hooks.pre': 'echo node pre',
      'tool_hooks.post': 'echo node post'
    }
  },
  { id: 'end', data: { label: 'End', shape: 'Msquare' } }
]
const edges = [
  { id: 'e1', source: 'start', target: 'tool_node' },
  { id: 'e2', source: 'tool_node', target: 'end' }
]
const graphAttrs = {
  'tool_hooks.pre': 'echo graph pre',
  'tool_hooks.post': 'echo graph post'
}
const dot = mod.generateDot('node_tool_hooks_probe', nodes, edges, graphAttrs)
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


def test_node_tool_hook_override_controls_present_item_6_6_02() -> None:
    assert_frontend_behavior_test_passed(
        "renders node-level tool hook override controls and warnings in sidebar and node toolbar"
    )


def test_tool_hook_warning_surfaces_present_item_6_6_03() -> None:
    assert_frontend_behavior_test_passed(
        "renders graph settings feedback for stylesheet diagnostics and tool hook warnings"
    )
    assert_frontend_behavior_test_passed(
        "renders node-level tool hook override controls and warnings in sidebar and node toolbar"
    )


def _probe_tool_hook_command_warning() -> dict[str, str | None]:
    repo_root = Path(__file__).resolve().parents[3]
    frontend_dir = repo_root / "frontend"

    with tempfile.TemporaryDirectory(prefix=".tmp-tool-hook-warning-", dir=frontend_dir) as temp_dir:
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
                str(frontend_dir / "src" / "lib" / "graphAttrValidation.ts"),
            ],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )

        probe_script = """
import { pathToFileURL } from 'node:url'
const mod = await import(pathToFileURL(process.env.GRAPH_ATTR_VALIDATION_JS_PATH).href)
console.log(JSON.stringify({
  valid: mod.getToolHookCommandWarning('echo hello'),
  embeddedApostrophe: mod.getToolHookCommandWarning(`echo "it's ok"`),
  newline: mod.getToolHookCommandWarning('echo hi\\necho there'),
  singleQuote: mod.getToolHookCommandWarning(\"echo 'unterminated\"),
  doubleQuote: mod.getToolHookCommandWarning('echo \"unterminated'),
}))
""".strip()

        env = os.environ.copy()
        env["GRAPH_ATTR_VALIDATION_JS_PATH"] = str(out_dir / "lib" / "graphAttrValidation.js")
        result = subprocess.run(
            ["node", "--input-type=module", "-e", probe_script],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        return json.loads(result.stdout)


def test_tool_hook_warning_heuristics_item_6_6_03() -> None:
    probe = _probe_tool_hook_command_warning()

    assert probe["valid"] is None
    assert probe["embeddedApostrophe"] is None
    assert probe["newline"] is not None and "single line" in probe["newline"].lower()
    assert probe["singleQuote"] is not None and "single quote" in probe["singleQuote"].lower()
    assert probe["doubleQuote"] is not None and "double quote" in probe["doubleQuote"].lower()


def test_node_tool_hook_overrides_round_trip_through_preview_item_6_6_02() -> None:
    flow = _generate_dot_with_node_tool_hook_overrides()
    payload = asyncio.run(server.preview_pipeline(server.PreviewRequest(flow_content=flow)))
    nodes = payload["graph"]["nodes"]
    tool_node = next((node for node in nodes if node["id"] == "tool_node"), None)

    assert tool_node is not None
    assert tool_node["tool_command"] == "echo run"
    assert tool_node["tool_hooks.pre"] == "echo node pre"
    assert tool_node["tool_hooks.post"] == "echo node post"

    graph_attrs = payload["graph"]["graph_attrs"]
    assert graph_attrs["tool_hooks.pre"] == "echo graph pre"
    assert graph_attrs["tool_hooks.post"] == "echo graph post"


def _save_loaded_tool_hook_graph_via_generate_dot(flow_content: str) -> str:
    repo_root = Path(__file__).resolve().parents[3]
    frontend_dir = repo_root / "frontend"

    preview = asyncio.run(server.preview_pipeline(server.PreviewRequest(flow_content=flow_content)))

    with tempfile.TemporaryDirectory(prefix=".tmp-dotutils-tool-hook-save-load-", dir=frontend_dir) as temp_dir:
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
                "Failed to compile dotUtils.ts for tool-hook save/load probe.\n"
                f"stdout:\n{compile_result.stdout}\n"
                f"stderr:\n{compile_result.stderr}"
            )

        probe_script = """
import { pathToFileURL } from 'node:url'
const mod = await import(pathToFileURL(process.env.DOT_UTILS_JS_PATH).href)
const preview = JSON.parse(process.env.PREVIEW_JSON)

const nodes = preview.graph.nodes.map((n) => ({
  id: n.id,
  data: {
    label: n.label,
    shape: n.shape ?? 'box',
    prompt: n.prompt ?? '',
    tool_command: n.tool_command ?? '',
    'tool_hooks.pre': n['tool_hooks.pre'] ?? '',
    'tool_hooks.post': n['tool_hooks.post'] ?? '',
    type: n.type ?? ''
  }
}))

const edges = preview.graph.edges.map((e, i) => ({
  id: `e-${e.from}-${e.to}-${i}`,
  source: e.from,
  target: e.to
}))

const dot = mod.generateDot('tool_hooks_save_load_probe', nodes, edges, preview.graph.graph_attrs || {})
console.log(dot)
""".strip()

        env = os.environ.copy()
        env["DOT_UTILS_JS_PATH"] = str(dot_utils_js)
        env["PREVIEW_JSON"] = json.dumps(preview)
        probe_result = subprocess.run(
            ["node", "--input-type=module", "-e", probe_script],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        return probe_result.stdout


def test_tool_hook_definitions_round_trip_through_save_load_item_6_6_04() -> None:
    flow = """
digraph tool_hook_save_load {
  graph [
    tool_hooks.pre="python ./hooks/pre.py --mode \\"global\\"",
    tool_hooks.post="./hooks/post.sh --emit report"
  ];
  start [label="Start", shape=Mdiamond];
  tool_node [
    label="Tool",
    shape=parallelogram,
    type=tool,
    tool_command="echo run",
    tool_hooks.pre="./hooks/node_pre.sh --flag",
    tool_hooks.post="python -c \\"print('done')\\""
  ];
  end [label="End", shape=Msquare];

  start -> tool_node;
  tool_node -> end;
}
""".strip()

    saved_dot = _save_loaded_tool_hook_graph_via_generate_dot(flow)
    payload = asyncio.run(server.preview_pipeline(server.PreviewRequest(flow_content=saved_dot)))

    graph_attrs = payload["graph"]["graph_attrs"]
    assert graph_attrs["tool_hooks.pre"] == 'python ./hooks/pre.py --mode "global"'
    assert graph_attrs["tool_hooks.post"] == "./hooks/post.sh --emit report"

    nodes = payload["graph"]["nodes"]
    tool_node = next((node for node in nodes if node["id"] == "tool_node"), None)
    assert tool_node is not None
    assert tool_node["tool_hooks.pre"] == "./hooks/node_pre.sh --flag"
    assert tool_node["tool_hooks.post"] == 'python -c "print(\'done\')"'



# ---- end tests/integration/test_ui_tool_hook_authoring.py ----
