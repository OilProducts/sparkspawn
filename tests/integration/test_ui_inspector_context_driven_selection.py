from pathlib import Path


def test_sidebar_resolves_inspector_scope_from_selection_context_item_4_1_03() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    sidebar_text = (repo_root / "frontend" / "src" / "components" / "Sidebar.tsx").read_text(encoding="utf-8")

    assert "type InspectorScope = 'none' | 'graph' | 'node' | 'edge'" in sidebar_text
    assert "function resolveInspectorScope(" in sidebar_text
    assert "if (viewMode !== 'editor') return 'none'" in sidebar_text
    assert "if (selectedEdgeId) return 'edge'" in sidebar_text
    assert "if (selectedNodeId) return 'node'" in sidebar_text
    assert "if (activeFlow) return 'graph'" in sidebar_text
    assert 'data-inspector-active-scope={activeInspectorScope}' in sidebar_text


