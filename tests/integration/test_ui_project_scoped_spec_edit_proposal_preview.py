from pathlib import Path


def test_projects_panel_exposes_spec_edit_proposal_preview_surface_item_5_5_03() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    projects_panel_text = (repo_root / "frontend" / "src" / "components" / "ProjectsPanel.tsx").read_text(encoding="utf-8")

    required_snippets = [
        'data-testid="project-spec-edit-proposal-surface"',
        "Spec Edit Proposals",
        "AI-generated spec edits appear here as explicit, reviewable proposals before any apply action.",
        'data-testid="project-spec-edit-proposal-preview"',
        "Proposal preview",
        "No proposed spec edits for this project yet.",
    ]

    for snippet in required_snippets:
        assert snippet in projects_panel_text, f"missing spec-edit proposal preview snippet: {snippet}"


def test_projects_panel_requires_active_project_for_spec_edit_proposal_preview_item_5_5_03() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    projects_panel_text = (repo_root / "frontend" / "src" / "components" / "ProjectsPanel.tsx").read_text(encoding="utf-8")

    required_snippets = [
        "Select an active project to review AI-generated spec edit proposals.",
        "Proposal artifacts are scoped to the active project context.",
    ]

    for snippet in required_snippets:
        assert snippet in projects_panel_text, f"missing active-project proposal preview scoping snippet: {snippet}"


