from __future__ import annotations

from pathlib import Path


def test_ui_save_failures_offer_actionable_remediation_for_item_5_3_02() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    store_text = (repo_root / "frontend" / "src" / "store.ts").read_text(encoding="utf-8")
    flow_persistence_text = (repo_root / "frontend" / "src" / "lib" / "flowPersistence.ts").read_text(encoding="utf-8")
    sidebar_text = (repo_root / "frontend" / "src" / "components" / "Sidebar.tsx").read_text(encoding="utf-8")
    run_stream_text = (repo_root / "frontend" / "src" / "components" / "RunStream.tsx").read_text(encoding="utf-8")

    assert "saveErrorKind" in store_text
    assert "markSaveFailure: (message: string, kind?: SaveErrorKind)" in store_text
    assert "saveErrorKind: 'conflict'" in store_text

    assert "retryLastSaveContent" in flow_persistence_text
    assert "markSaveFailure(`Flow save failed: ${message}`, 'network')" in flow_persistence_text
    assert "detail.status === 'parse_error'" in flow_persistence_text
    assert "detail.status === 'validation_error'" in flow_persistence_text

    assert 'data-testid="save-remediation-hint"' in sidebar_text
    assert 'data-testid="save-remediation-retry"' in sidebar_text
    assert "retryLastSaveContent" in sidebar_text
    assert "resolveSaveRemediation" in sidebar_text

    assert 'data-testid="global-save-remediation-hint"' in run_stream_text
    assert "resolveSaveRemediation" in run_stream_text


def test_checklist_marks_item_5_3_02_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")
    assert "- [x] [5.3-02]" in checklist_text
