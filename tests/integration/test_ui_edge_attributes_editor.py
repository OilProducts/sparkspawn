from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

import attractor.api.server as server


def _generate_dot_with_edge_attrs() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    frontend_dir = repo_root / "frontend"

    with tempfile.TemporaryDirectory(prefix=".tmp-dotutils-edge-attrs-", dir=frontend_dir) as temp_dir:
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
