from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path

import attractor.api.server as server


def _generate_dot_with_all_handler_types() -> str:
    repo_root = Path(__file__).resolve().parents[2]
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


