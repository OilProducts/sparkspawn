from pathlib import Path


def test_structured_form_editing_surfaces_graph_node_and_edge_item_5_2_02() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    graph_settings_text = (repo_root / "frontend" / "src" / "components" / "GraphSettings.tsx").read_text(encoding="utf-8")
    sidebar_text = (repo_root / "frontend" / "src" / "components" / "Sidebar.tsx").read_text(encoding="utf-8")

    assert 'data-testid="graph-structured-form"' in graph_settings_text
    assert 'label className="text-xs font-medium text-foreground">Goal</label>' in graph_settings_text
    assert 'label className="text-xs font-medium text-foreground">Label</label>' in graph_settings_text

    assert 'data-testid="node-structured-form"' in sidebar_text
    assert '<label className="text-sm font-medium">Label</label>' in sidebar_text
    assert '<label className="text-sm font-medium">Shape / Type</label>' in sidebar_text

    assert 'data-testid="edge-structured-form"' in sidebar_text
    assert '<label className="text-sm font-medium">Condition</label>' in sidebar_text
    assert '<label className="text-sm font-medium">Weight</label>' in sidebar_text


def test_checklist_marks_item_5_2_02_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [5.2-02]" in checklist_text
