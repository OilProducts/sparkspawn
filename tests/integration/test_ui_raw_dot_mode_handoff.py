from pathlib import Path


def test_raw_dot_mode_exposes_safe_handoff_controls_item_5_2_03() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    editor_text = (repo_root / "frontend" / "src" / "components" / "Editor.tsx").read_text(encoding="utf-8")

    assert 'data-testid="editor-mode-toggle"' in editor_text
    assert 'Raw DOT' in editor_text
    assert 'data-testid="raw-dot-editor"' in editor_text
    assert 'data-testid="raw-dot-handoff-error"' in editor_text
    assert 'Safe handoff requires valid DOT.' in editor_text
    assert "if (editorMode === 'raw') return;" in editor_text
    assert 'disabled={editorMode === \'raw\'}' in editor_text


def test_checklist_marks_item_5_2_03_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [5.2-03]" in checklist_text
