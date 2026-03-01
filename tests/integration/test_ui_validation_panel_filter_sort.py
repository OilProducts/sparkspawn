from __future__ import annotations

from pathlib import Path


def test_validation_panel_supports_filter_and_sort_controls_item_7_1_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    validation_panel_text = (
        repo_root / "frontend" / "src" / "components" / "ValidationPanel.tsx"
    ).read_text(encoding="utf-8")

    assert 'data-testid="validation-panel"' in validation_panel_text
    assert 'data-testid="validation-sort-select"' in validation_panel_text
    assert "validation-filter-all" in validation_panel_text
    assert "validation-filter-error" in validation_panel_text
    assert "validation-filter-warning" in validation_panel_text
    assert "validation-filter-info" in validation_panel_text
    assert "const filteredDiagnostics = diagnostics.filter((diag) =>" in validation_panel_text
    assert "const sortedDiagnostics = [...filteredDiagnostics].sort((left, right) => {" in validation_panel_text
    assert 'data-testid="validation-diagnostic-item"' in validation_panel_text


def test_ui_smoke_covers_validation_panel_filter_and_sort_item_7_1_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    ui_smoke_text = (repo_root / "frontend" / "e2e" / "ui-smoke.spec.ts").read_text(encoding="utf-8")

    assert "validation panel supports filter and sort controls for item 7.1-01" in ui_smoke_text
    assert "13-validation-panel-filter-sort.png" in ui_smoke_text
    assert "validation-filter-warning" in ui_smoke_text
    assert "validation-sort-select" in ui_smoke_text


def test_checklist_marks_item_7_1_01_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [7.1-01]" in checklist_text
