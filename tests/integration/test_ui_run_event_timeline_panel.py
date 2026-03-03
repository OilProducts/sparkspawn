from __future__ import annotations

from pathlib import Path


def test_runs_panel_renders_typed_event_timeline_from_sse_item_9_4_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    runs_panel_text = (repo_root / "frontend" / "src" / "components" / "RunsPanel.tsx").read_text(encoding="utf-8")

    required_snippets = [
        "const source = new EventSource(`/pipelines/${encodeURIComponent(selectedRunTimelineId)}/events`)",
        "const TIMELINE_EVENT_TYPES: Record<string, TimelineEventCategory> = {",
        "PipelineStarted: 'lifecycle'",
        "StageStarted: 'stage'",
        "ParallelStarted: 'parallel'",
        "InterviewStarted: 'interview'",
        "CheckpointSaved: 'checkpoint'",
        "data-testid=\"run-event-timeline-panel\"",
        "data-testid=\"run-event-timeline-row\"",
        "data-testid=\"run-event-timeline-row-type\"",
        "data-testid=\"run-event-timeline-row-category\"",
        "data-testid=\"run-event-timeline-row-summary\"",
    ]

    for snippet in required_snippets:
        assert snippet in runs_panel_text, f"missing run event timeline snippet: {snippet}"


def test_ui_smoke_includes_event_timeline_visual_qa_item_9_4_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    ui_smoke_text = (repo_root / "frontend" / "e2e" / "ui-smoke.spec.ts").read_text(encoding="utf-8")

    assert "run event timeline renders typed lifecycle and runtime events for item 9.4-01" in ui_smoke_text
    assert "await page.addInitScript((targetRunId: string) => {" in ui_smoke_text
    assert "emit({ type: \"PipelineStarted\", current_node: \"start\" })" in ui_smoke_text
    assert "emit({ type: \"CheckpointSaved\", node_id: \"review\", persisted: true })" in ui_smoke_text
    assert "await expect(page.getByTestId(\"run-event-timeline-row-type\")).toHaveCount(4)" in ui_smoke_text
    assert "await expect(page.getByTestId(\"run-event-timeline-row-type\")).toHaveCount(5)" in ui_smoke_text
    assert "08i-runs-panel-event-timeline.png" in ui_smoke_text
    assert "run-event-timeline-row-type" in ui_smoke_text
    assert "run-event-timeline-row-category" in ui_smoke_text
