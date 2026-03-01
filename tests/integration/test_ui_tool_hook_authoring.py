from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

import attractor.api.server as server


def test_graph_settings_exposes_graph_scope_tool_hook_fields_item_6_6_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    graph_settings_text = (repo_root / "frontend" / "src" / "components" / "GraphSettings.tsx").read_text(encoding="utf-8")

    assert 'data-testid="graph-attr-input-tool_hooks.pre"' in graph_settings_text
    assert 'data-testid="graph-attr-input-tool_hooks.post"' in graph_settings_text
    assert "updateGraphAttr('tool_hooks.pre'" in graph_settings_text
    assert "updateGraphAttr('tool_hooks.post'" in graph_settings_text


def _generate_dot_with_node_tool_hook_overrides() -> str:
    repo_root = Path(__file__).resolve().parents[2]
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
    repo_root = Path(__file__).resolve().parents[2]
    sidebar_text = (repo_root / "frontend" / "src" / "components" / "Sidebar.tsx").read_text(encoding="utf-8")
    task_node_text = (repo_root / "frontend" / "src" / "components" / "TaskNode.tsx").read_text(encoding="utf-8")

    assert 'data-testid="node-attr-input-tool_hooks.pre"' in sidebar_text
    assert 'data-testid="node-attr-input-tool_hooks.post"' in sidebar_text
    assert "handlePropertyChange('tool_hooks.pre'" in sidebar_text
    assert "handlePropertyChange('tool_hooks.post'" in sidebar_text

    assert 'data-testid="node-toolbar-attr-input-tool_hooks.pre"' in task_node_text
    assert 'data-testid="node-toolbar-attr-input-tool_hooks.post"' in task_node_text
    assert "'tool_hooks.pre': draftToolHooksPre" in task_node_text
    assert "'tool_hooks.post': draftToolHooksPost" in task_node_text


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


def test_checklist_marks_item_6_6_01_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [6.6-01]" in checklist_text


def test_checklist_marks_item_6_6_02_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [6.6-02]" in checklist_text
