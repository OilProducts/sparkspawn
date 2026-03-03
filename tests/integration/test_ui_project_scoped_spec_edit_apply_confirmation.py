from pathlib import Path


def test_projects_panel_requires_explicit_confirmation_before_applying_spec_edits_item_5_5_04() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    projects_panel_text = (repo_root / "frontend" / "src" / "components" / "ProjectsPanel.tsx").read_text(encoding="utf-8")

    required_snippets = [
        'data-testid="project-spec-edit-proposal-apply-button"',
        "Apply proposal",
        "if (!window.confirm('Apply these proposed spec edits to the active project spec?')) {",
        "return",
    ]

    for snippet in required_snippets:
        assert snippet in projects_panel_text, f"missing explicit apply confirmation snippet: {snippet}"


