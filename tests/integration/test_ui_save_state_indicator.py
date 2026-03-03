from __future__ import annotations

from pathlib import Path


def test_ui_save_state_indicator_supports_conflict_state_for_item_5_3_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    store_text = (repo_root / "frontend" / "src" / "store.ts").read_text(encoding="utf-8")
    flow_persistence_text = (repo_root / "frontend" / "src" / "lib" / "flowPersistence.ts").read_text(encoding="utf-8")
    sidebar_text = (repo_root / "frontend" / "src" / "components" / "Sidebar.tsx").read_text(encoding="utf-8")
    run_stream_text = (repo_root / "frontend" / "src" / "components" / "RunStream.tsx").read_text(encoding="utf-8")

    assert "export type SaveState = 'idle' | 'saving' | 'saved' | 'error' | 'conflict'" in store_text
    assert "markSaveConflict" in store_text
    assert "saveState: 'conflict'" in store_text

    assert "status === 'conflict'" in flow_persistence_text or "response.status === 409" in flow_persistence_text
    assert "markSaveConflict" in flow_persistence_text

    assert "saveState === 'conflict'" in sidebar_text
    assert "Save Conflict" in sidebar_text
    assert "saveState === 'conflict'" in run_stream_text
    assert "Save Conflict" in run_stream_text


