from pathlib import Path


def test_inspector_scaffold_is_shared_across_graph_node_and_edge_item_2_06() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    scaffold_path = repo_root / "frontend" / "src" / "components" / "InspectorScaffold.tsx"
    sidebar_path = repo_root / "frontend" / "src" / "components" / "Sidebar.tsx"
    graph_settings_path = repo_root / "frontend" / "src" / "components" / "GraphSettings.tsx"

    assert scaffold_path.exists(), "missing shared inspector scaffold component for checklist item 2-06"

    scaffold_text = scaffold_path.read_text(encoding="utf-8")
    assert "data-testid=\"inspector-scaffold\"" in scaffold_text
    assert "data-testid=\"inspector-empty-state\"" in scaffold_text
    assert "scopeLabel" in scaffold_text

    sidebar_text = sidebar_path.read_text(encoding="utf-8")
    assert "import { InspectorScaffold, InspectorEmptyState } from './InspectorScaffold'" in sidebar_text
    assert "import { GraphSettings } from './GraphSettings'" in sidebar_text
    assert "<GraphSettings inline />" in sidebar_text
    assert "scopeLabel=\"Node\"" in sidebar_text
    assert "scopeLabel=\"Edge\"" in sidebar_text

    graph_settings_text = graph_settings_path.read_text(encoding="utf-8")
    assert "import { InspectorScaffold } from './InspectorScaffold'" in graph_settings_text
    assert "scopeLabel=\"Graph\"" in graph_settings_text
    assert "inline?: boolean" in graph_settings_text
    assert "if (inline) {" in graph_settings_text

    editor_text = (repo_root / "frontend" / "src" / "components" / "Editor.tsx").read_text(encoding="utf-8")
    assert "import { GraphSettings } from './GraphSettings'" not in editor_text
    assert "<GraphSettings />" not in editor_text


def test_checklist_marks_item_2_06_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [2-06]" in checklist_text
