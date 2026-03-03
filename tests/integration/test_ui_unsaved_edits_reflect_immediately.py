from pathlib import Path
import re


def test_sidebar_prompt_field_updates_node_data_on_each_change_item_5_1_03() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    sidebar_text = (repo_root / "frontend" / "src" / "components" / "Sidebar.tsx").read_text(encoding="utf-8")

    required_snippets = [
        "value={(selectedNode?.data?.prompt as string) || ''}",
        "onChange={(e) => handlePropertyChange('prompt', e.target.value)}",
    ]
    for snippet in required_snippets:
        assert snippet in sidebar_text, f"missing immediate prompt sync snippet: {snippet}"


def test_live_preview_runs_before_save_debounce_item_5_1_03() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    editor_text = (repo_root / "frontend" / "src" / "components" / "Editor.tsx").read_text(encoding="utf-8")
    sidebar_text = (repo_root / "frontend" / "src" / "components" / "Sidebar.tsx").read_text(encoding="utf-8")

    preview_match = re.search(r"const LIVE_PREVIEW_DEBOUNCE_MS = (\d+)", editor_text)
    save_match = re.search(r"const INSPECTOR_SAVE_DEBOUNCE_MS = (\d+)", sidebar_text)

    assert preview_match, "missing live preview debounce constant in editor"
    assert save_match, "missing inspector save debounce constant in sidebar"

    preview_ms = int(preview_match.group(1))
    save_ms = int(save_match.group(1))
    assert preview_ms < save_ms, "live diagnostics preview should run before debounced save persistence"

