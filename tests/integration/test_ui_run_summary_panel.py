from pathlib import Path


def test_runs_panel_renders_run_summary_fields_item_9_1_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    runs_panel_text = (repo_root / "frontend" / "src" / "components" / "RunsPanel.tsx").read_text(encoding="utf-8")

    required_test_ids = [
        "data-testid=\"run-summary-panel\"",
        "data-testid=\"run-summary-status\"",
        "data-testid=\"run-summary-result\"",
        "data-testid=\"run-summary-flow-name\"",
        "data-testid=\"run-summary-started-at\"",
        "data-testid=\"run-summary-ended-at\"",
        "data-testid=\"run-summary-duration\"",
        "data-testid=\"run-summary-model\"",
        "data-testid=\"run-summary-working-directory\"",
        "data-testid=\"run-summary-project-path\"",
        "data-testid=\"run-summary-git-branch\"",
        "data-testid=\"run-summary-git-commit\"",
        "data-testid=\"run-summary-last-error\"",
        "data-testid=\"run-summary-token-usage\"",
    ]
    required_labels = [
        "Status:",
        "Result:",
        "Flow:",
        "Started:",
        "Ended:",
        "Duration:",
        "Model:",
        "Working Dir:",
        "Project Path:",
        "Git Branch:",
        "Git Commit:",
        "Last Error:",
        "Tokens:",
    ]

    for snippet in required_test_ids:
        assert snippet in runs_panel_text, f"missing run summary panel snippet: {snippet}"
    for label in required_labels:
        assert label in runs_panel_text, f"missing run summary label: {label}"


def test_runs_panel_project_path_prefers_project_metadata_item_9_1_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    runs_panel_text = (repo_root / "frontend" / "src" / "components" / "RunsPanel.tsx").read_text(encoding="utf-8")

    assert "selectedRunSummary.project_path || activeProjectPath || '—'" in runs_panel_text


def test_ui_smoke_includes_populated_run_summary_visual_qa_item_9_1_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    ui_smoke_text = (repo_root / "frontend" / "e2e" / "ui-smoke.spec.ts").read_text(encoding="utf-8")

    assert "run summary panel renders populated metadata for item 9.1-01" in ui_smoke_text
    assert "08b-runs-panel-populated-summary.png" in ui_smoke_text
