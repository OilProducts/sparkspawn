from __future__ import annotations

from pathlib import Path


def test_ui_save_paths_expose_user_visible_failure_state_for_item_2_02() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    save_helper_path = repo_root / "frontend" / "src" / "lib" / "flowPersistence.ts"
    store_path = repo_root / "frontend" / "src" / "store.ts"
    sidebar_path = repo_root / "frontend" / "src" / "components" / "Sidebar.tsx"
    run_stream_path = repo_root / "frontend" / "src" / "components" / "RunStream.tsx"
    editor_path = repo_root / "frontend" / "src" / "components" / "Editor.tsx"
    graph_settings_path = repo_root / "frontend" / "src" / "components" / "GraphSettings.tsx"
    task_node_path = repo_root / "frontend" / "src" / "components" / "TaskNode.tsx"

    assert save_helper_path.exists(), "missing shared flow persistence helper for item 2-02"
    save_helper_text = save_helper_path.read_text(encoding="utf-8")
    assert "saveFlowContent" in save_helper_text
    assert "status === 'parse_error'" in save_helper_text
    assert "status === 'validation_error'" in save_helper_text

    store_text = store_path.read_text(encoding="utf-8")
    assert "saveState" in store_text
    assert "saveErrorMessage" in store_text
    assert "markSaveInFlight" in store_text
    assert "markSaveSuccess" in store_text
    assert "markSaveFailure" in store_text

    sidebar_text = sidebar_path.read_text(encoding="utf-8")
    assert 'data-testid="save-state-indicator"' in sidebar_text
    assert "saveStateLabel" in sidebar_text
    assert "saveErrorMessage" in sidebar_text

    run_stream_text = run_stream_path.read_text(encoding="utf-8")
    assert 'data-testid="global-save-state-indicator"' in run_stream_text
    assert "saveStateLabel" in run_stream_text
    assert "saveErrorMessage" in run_stream_text

    for path in (editor_path, graph_settings_path, sidebar_path, task_node_path):
        text = path.read_text(encoding="utf-8")
        assert "saveFlowContent" in text, f"{path.name} must use shared flow save helper"

    editor_text = editor_path.read_text(encoding="utf-8")
    graph_settings_text = graph_settings_path.read_text(encoding="utf-8")
    assert "beforeunload" in editor_text
    assert "flushPendingSave" in editor_text
    assert "flushPendingSave" in graph_settings_text


def test_checklist_marks_item_2_02_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")
    assert "- [x] [2-02]" in checklist_text
