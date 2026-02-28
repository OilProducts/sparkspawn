from pathlib import Path


def test_projects_panel_renders_glanceable_project_metadata_item_4_3_06() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    projects_panel_text = (repo_root / "frontend" / "src" / "components" / "ProjectsPanel.tsx").read_text(encoding="utf-8")

    required_snippets = [
        "const [projectBranches, setProjectBranches] = useState<Record<string, string | null>>({})",
        "const projectName = project.directoryPath.split('/').filter(Boolean).pop() || project.directoryPath",
        "const branchLabel = projectBranches[project.directoryPath] || \"Unknown branch\"",
        "const formatLastActivity = (value: string | null) =>",
        'data-testid="project-metadata-name"',
        'data-testid="project-metadata-directory"',
        'data-testid="project-metadata-branch"',
        'data-testid="project-metadata-last-activity"',
    ]

    for snippet in required_snippets:
        assert snippet in projects_panel_text, f"missing project metadata UI snippet: {snippet}"


def test_checklist_marks_item_4_3_06_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [4.3-06]" in checklist_text
