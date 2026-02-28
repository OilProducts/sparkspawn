from __future__ import annotations

from pathlib import Path


def test_graph_settings_uses_progressive_disclosure_for_advanced_fields_item_2_03() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    graph_settings_path = repo_root / "frontend" / "src" / "components" / "GraphSettings.tsx"

    graph_settings_text = graph_settings_path.read_text(encoding="utf-8")

    assert "const [showAdvancedGraphAttrs, setShowAdvancedGraphAttrs] = useState(false)" in graph_settings_text
    assert 'data-testid="graph-advanced-toggle"' in graph_settings_text
    assert "showAdvancedGraphAttrs ? 'Hide Advanced Fields' : 'Show Advanced Fields'" in graph_settings_text
    assert "{showAdvancedGraphAttrs && (" in graph_settings_text

    # Advanced fields must remain fully editable after disclosure.
    assert "updateGraphAttr('model_stylesheet'" in graph_settings_text
    assert "updateGraphAttr('retry_target'" in graph_settings_text
    assert "updateGraphAttr('fallback_retry_target'" in graph_settings_text


def test_checklist_marks_item_2_03_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [2-03]" in checklist_text
