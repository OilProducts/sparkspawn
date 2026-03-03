from __future__ import annotations

from pathlib import Path


def test_ui_exposes_routing_retry_and_failure_explainability_views_item_2_04() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    panel_path = repo_root / "frontend" / "src" / "components" / "ExplainabilityPanel.tsx"
    terminal_path = repo_root / "frontend" / "src" / "components" / "Terminal.tsx"

    assert panel_path.exists(), "missing ExplainabilityPanel component for checklist item 2-04"
    panel_text = panel_path.read_text(encoding="utf-8")

    assert 'data-testid="routing-explainability-view"' in panel_text
    assert 'data-testid="retry-explainability-view"' in panel_text
    assert 'data-testid="failure-explainability-view"' in panel_text
    assert "new EventSource(`/pipelines/${encodeURIComponent(selectedRunId)}/events`)" in panel_text
    assert "data.type === 'StageStarted'" in panel_text
    assert "data.type === 'StageRetrying'" in panel_text
    assert "data.type === 'StageFailed'" in panel_text
    assert "data.type === 'PipelineRestarted'" in panel_text

    terminal_text = terminal_path.read_text(encoding="utf-8")
    assert "ExplainabilityPanel" in terminal_text
    assert "<ExplainabilityPanel />" in terminal_text


