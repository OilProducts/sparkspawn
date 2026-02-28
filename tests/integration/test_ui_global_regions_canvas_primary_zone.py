from pathlib import Path


def test_editor_and_execution_modes_keep_canvas_workspace_primary_item_4_1_02() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_path = repo_root / "frontend" / "src" / "App.tsx"
    app_text = app_path.read_text(encoding="utf-8")

    required_snippets = [
        "const isCanvasMode = viewMode === 'editor' || viewMode === 'execution'",
        "{isCanvasMode ? (",
        'data-testid="canvas-workspace-primary"',
        'data-testid="editor-panel"',
        "flex-1 w-full h-full bg-background/50",
        "<Editor />",
    ]

    for snippet in required_snippets:
        assert snippet in app_text, f"missing canvas-primary workspace snippet: {snippet}"


def test_checklist_marks_item_4_1_02_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [4.1-02]" in checklist_text
