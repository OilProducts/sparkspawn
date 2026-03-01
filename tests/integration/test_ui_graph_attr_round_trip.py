from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path

import attractor.api.server as server


def _generate_dot_with_graph_attrs(graph_attrs: dict[str, object]) -> str:
    repo_root = Path(__file__).resolve().parents[2]
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


def test_checklist_marks_item_6_1_04_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [6.1-04]" in checklist_text
