from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


def _resolve_stylesheet_preview(stylesheet: str, nodes: list[dict[str, str]], graph_defaults: dict[str, str]) -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    frontend_dir = repo_root / "frontend"

    with tempfile.TemporaryDirectory(prefix=".tmp-stylesheet-preview-", dir=frontend_dir) as temp_dir:
        temp_path = Path(temp_dir)
        out_dir = temp_path / "out"
        out_dir.mkdir(parents=True, exist_ok=True)

        probe_tsconfig = temp_path / "tsconfig.json"
        probe_tsconfig.write_text(
            """{
  \"extends\": \"../tsconfig.app.json\",
  \"compilerOptions\": {
    \"noEmit\": false,
    \"noEmitOnError\": false,
    \"allowImportingTsExtensions\": false,
    \"outDir\": \"./out\"
  },
  \"include\": [\"../src/lib/modelStylesheetPreview.ts\"]
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

        preview_js = out_dir / "modelStylesheetPreview.js"
        if not preview_js.exists():
            raise AssertionError(
                "Failed to compile modelStylesheetPreview.ts for selector/effective preview probe.\n"
                f"stdout:\n{compile_result.stdout}\n"
                f"stderr:\n{compile_result.stderr}"
            )

        probe_script = """
import { pathToFileURL } from 'node:url'
const mod = await import(pathToFileURL(process.env.MODEL_STYLESHEET_PREVIEW_JS_PATH).href)
const stylesheet = process.env.STYLESHEET
const nodes = JSON.parse(process.env.NODES_JSON)
const graphDefaults = JSON.parse(process.env.GRAPH_DEFAULTS_JSON)
const result = mod.resolveModelStylesheetPreview(stylesheet, nodes, graphDefaults)
console.log(JSON.stringify(result))
""".strip()

        env = os.environ.copy()
        env.update(
            {
                "MODEL_STYLESHEET_PREVIEW_JS_PATH": str(preview_js),
                "STYLESHEET": stylesheet,
                "NODES_JSON": json.dumps(nodes),
                "GRAPH_DEFAULTS_JSON": json.dumps(graph_defaults),
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

        return json.loads(probe_result.stdout)


def test_graph_settings_exposes_stylesheet_selector_and_effective_preview_item_6_5_03() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    graph_settings_text = (
        repo_root / "frontend" / "src" / "components" / "GraphSettings.tsx"
    ).read_text(encoding="utf-8")

    assert 'data-testid="graph-model-stylesheet-selector-preview"' in graph_settings_text
    assert 'data-testid="graph-model-stylesheet-effective-preview"' in graph_settings_text
    assert "Matching selectors" in graph_settings_text
    assert "Effective per-node values" in graph_settings_text


def test_stylesheet_preview_resolves_selector_matches_and_effective_values_item_6_5_03() -> None:
    preview = _resolve_stylesheet_preview(
        stylesheet='* { llm_provider: style-provider; } .fast { llm_model: style-model; } #review { reasoning_effort: low; }',
        nodes=[
            {
                "id": "draft",
                "class": "fast",
                "llm_model": "",
                "llm_provider": "",
                "reasoning_effort": "",
            },
            {
                "id": "review",
                "class": "fast,critical",
                "llm_model": "node-model",
                "llm_provider": "",
                "reasoning_effort": "",
            },
            {
                "id": "ship",
                "class": "",
                "llm_model": "",
                "llm_provider": "",
                "reasoning_effort": "",
            },
        ],
        graph_defaults={
            "llm_model": "default-model",
            "llm_provider": "default-provider",
            "reasoning_effort": "medium",
        },
    )

    selector_preview = {entry["selector"]: entry for entry in preview["selectorPreview"]}
    assert selector_preview["*"]["matchedNodeIds"] == ["draft", "review", "ship"]
    assert selector_preview[".fast"]["matchedNodeIds"] == ["draft", "review"]
    assert selector_preview["#review"]["matchedNodeIds"] == ["review"]

    node_preview = {entry["nodeId"]: entry for entry in preview["nodePreview"]}
    assert node_preview["draft"]["effective"]["llm_model"] == {"value": "style-model", "source": "stylesheet"}
    assert node_preview["review"]["effective"]["llm_model"] == {"value": "node-model", "source": "node"}
    assert node_preview["ship"]["effective"]["llm_model"] == {"value": "default-model", "source": "graph_default"}
    assert node_preview["review"]["effective"]["reasoning_effort"] == {"value": "low", "source": "stylesheet"}


def test_graph_settings_exposes_precedence_rendering_guidance_item_6_5_04() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    graph_settings_text = (
        repo_root / "frontend" / "src" / "components" / "GraphSettings.tsx"
    ).read_text(encoding="utf-8")

    assert 'data-testid="graph-model-stylesheet-precedence-guidance"' in graph_settings_text
    assert "Precedence: node attr &gt; stylesheet &gt; graph default &gt; system default." in graph_settings_text


def test_stylesheet_preview_resolves_precedence_sources_item_6_5_04() -> None:
    preview = _resolve_stylesheet_preview(
        stylesheet=".style { llm_model: style-model; llm_provider: style-provider; }",
        nodes=[
            {
                "id": "node_override",
                "class": "style",
                "llm_model": "node-model",
                "llm_provider": "",
                "reasoning_effort": "",
            },
            {
                "id": "stylesheet_only",
                "class": "style",
                "llm_model": "",
                "llm_provider": "",
                "reasoning_effort": "",
            },
            {
                "id": "graph_default_only",
                "class": "",
                "llm_model": "",
                "llm_provider": "",
                "reasoning_effort": "",
            },
            {
                "id": "system_default_only",
                "class": "",
                "llm_model": "",
                "llm_provider": "",
                "reasoning_effort": "",
            },
        ],
        graph_defaults={
            "llm_model": "graph-model",
            "llm_provider": "",
            "reasoning_effort": "",
        },
    )

    node_preview = {entry["nodeId"]: entry for entry in preview["nodePreview"]}
    assert node_preview["node_override"]["effective"]["llm_model"] == {"value": "node-model", "source": "node"}
    assert node_preview["stylesheet_only"]["effective"]["llm_provider"] == {"value": "style-provider", "source": "stylesheet"}
    assert node_preview["graph_default_only"]["effective"]["llm_model"] == {"value": "graph-model", "source": "graph_default"}
    assert node_preview["system_default_only"]["effective"]["reasoning_effort"] == {"value": "high", "source": "system_default"}


def test_graph_settings_renders_effective_source_labels_item_6_5_04() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    graph_settings_text = (
        repo_root / "frontend" / "src" / "components" / "GraphSettings.tsx"
    ).read_text(encoding="utf-8")

    assert "MODEL_VALUE_SOURCE_LABEL[node.effective.llm_model.source]" in graph_settings_text
    assert "MODEL_VALUE_SOURCE_LABEL[node.effective.llm_provider.source]" in graph_settings_text
    assert "MODEL_VALUE_SOURCE_LABEL[node.effective.reasoning_effort.source]" in graph_settings_text
    assert "graph_default: 'graph default'" in graph_settings_text


def test_checklist_marks_item_6_5_03_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [6.5-03]" in checklist_text


def test_checklist_marks_item_6_5_04_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [6.5-04]" in checklist_text
