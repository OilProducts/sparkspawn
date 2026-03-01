from __future__ import annotations

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


def _run_dot_utils_probe(probe_script: str, *, temp_prefix: str) -> str:
    repo_root = Path(__file__).resolve().parents[2]
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
    repo_root = Path(__file__).resolve().parents[2]
    sidebar_text = (repo_root / "frontend" / "src" / "components" / "Sidebar.tsx").read_text(encoding="utf-8")

    assert 'data-testid="edge-structured-form"' in sidebar_text
    assert "Label" in sidebar_text
    assert "Condition" in sidebar_text
    assert "Weight" in sidebar_text
    assert "Fidelity" in sidebar_text
    assert "Thread ID" in sidebar_text
    assert "Loop Restart" in sidebar_text

    assert "handleEdgePropertyChange('label'" in sidebar_text
    assert "handleEdgePropertyChange('condition'" in sidebar_text
    assert "handleEdgePropertyChange('weight'" in sidebar_text
    assert "handleEdgePropertyChange('fidelity'" in sidebar_text
    assert "handleEdgePropertyChange('thread_id'" in sidebar_text
    assert "handleEdgePropertyChange('loop_restart'" in sidebar_text


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


def test_checklist_marks_item_6_3_01_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [6.3-01]" in checklist_text


def test_edge_condition_field_exposes_syntax_hints_and_preview_feedback_item_6_3_02() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    sidebar_text = (repo_root / "frontend" / "src" / "components" / "Sidebar.tsx").read_text(encoding="utf-8")

    assert 'data-testid="edge-condition-syntax-hints"' in sidebar_text
    assert "Use && to join clauses" in sidebar_text
    assert "Supported keys: outcome, preferred_label, context.<path>" in sidebar_text
    assert "Operators: = or !=" in sidebar_text

    assert "const edgeDiagnostics = useStore((state) => state.edgeDiagnostics)" in sidebar_text
    assert "const selectedEdgeDiagnosticKey = selectedEdge ? `${selectedEdge.source}->${selectedEdge.target}` : null" in sidebar_text
    assert "const selectedEdgeConditionDiagnostics = selectedEdgeDiagnosticKey" in sidebar_text
    assert "diag.rule_id === 'condition_syntax'" in sidebar_text
    assert 'data-testid="edge-condition-preview-feedback"' in sidebar_text
    assert "Condition syntax looks valid in preview." in sidebar_text


def test_checklist_marks_item_6_3_02_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [6.3-02]" in checklist_text


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


def test_checklist_marks_item_6_3_03_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [6.3-03]" in checklist_text
