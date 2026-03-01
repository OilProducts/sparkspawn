from __future__ import annotations

from pathlib import Path


def test_graph_settings_exposes_all_required_graph_attributes_item_6_1_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    graph_settings_text = (repo_root / "frontend" / "src" / "components" / "GraphSettings.tsx").read_text(encoding="utf-8")

    required_update_calls = [
        "updateGraphAttr('goal'",
        "updateGraphAttr('label'",
        "updateGraphAttr('model_stylesheet'",
        "updateGraphAttr('default_max_retry'",
        "updateGraphAttr('default_fidelity'",
        "updateGraphAttr('retry_target'",
        "updateGraphAttr('fallback_retry_target'",
        "updateGraphAttr('stack.child_dotfile'",
        "updateGraphAttr('stack.child_workdir'",
        "updateGraphAttr('tool_hooks.pre'",
        "updateGraphAttr('tool_hooks.post'",
    ]

    for call in required_update_calls:
        assert call in graph_settings_text

    assert "Stack Child Dotfile" in graph_settings_text
    assert "Stack Child Workdir" in graph_settings_text
    assert "Tool Hooks Pre" in graph_settings_text
    assert "Tool Hooks Post" in graph_settings_text


def test_store_and_dot_generation_include_required_graph_attributes_item_6_1_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    store_text = (repo_root / "frontend" / "src" / "store.ts").read_text(encoding="utf-8")
    dot_utils_text = (repo_root / "frontend" / "src" / "lib" / "dotUtils.ts").read_text(encoding="utf-8")

    for attr_key in ("stack.child_dotfile", "stack.child_workdir", "tool_hooks.pre", "tool_hooks.post"):
        assert f"'{attr_key}'" in dot_utils_text

    assert "'stack.child_dotfile'?: string" in store_text
    assert "'stack.child_workdir'?: string" in store_text
    assert "'tool_hooks.pre'?: string" in store_text
    assert "'tool_hooks.post'?: string" in store_text


def test_checklist_marks_item_6_1_01_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [6.1-01]" in checklist_text
