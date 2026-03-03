from pathlib import Path


def test_sidebar_prompt_field_updates_node_data_on_each_change_item_5_1_03() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    sidebar_text = (repo_root / "frontend" / "src" / "components" / "Sidebar.tsx").read_text(encoding="utf-8")

    required_snippets = [
        "value={(selectedNode?.data?.prompt as string) || ''}",
        "onChange={(e) => handlePropertyChange('prompt', e.target.value)}",
    ]
    for snippet in required_snippets:
        assert snippet in sidebar_text, f"missing immediate prompt sync snippet: {snippet}"


