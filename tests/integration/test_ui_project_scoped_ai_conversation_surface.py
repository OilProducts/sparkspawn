from pathlib import Path


def test_projects_panel_exposes_project_scoped_ai_conversation_surface_item_5_5_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    projects_panel_text = (repo_root / "frontend" / "src" / "components" / "ProjectsPanel.tsx").read_text(encoding="utf-8")

    required_snippets = [
        'data-testid="project-ai-conversation-surface"',
        "Project-Scoped AI Conversation",
        'data-testid="project-ai-conversation-start-button"',
        'data-testid="project-ai-conversation-continue-button"',
        "Start conversation",
        "Continue conversation",
    ]

    for snippet in required_snippets:
        assert snippet in projects_panel_text, f"missing project-scoped AI conversation surface snippet: {snippet}"


def test_projects_panel_requires_active_project_for_ai_conversation_surface_item_5_5_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    projects_panel_text = (repo_root / "frontend" / "src" / "components" / "ProjectsPanel.tsx").read_text(encoding="utf-8")

    required_snippets = [
        "Select an active project to start or continue a project-scoped AI conversation.",
        "No project conversation selected yet.",
    ]

    for snippet in required_snippets:
        assert snippet in projects_panel_text, f"missing active-project AI conversation scoping snippet: {snippet}"


def test_checklist_marks_item_5_5_01_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [5.5-01]" in checklist_text
