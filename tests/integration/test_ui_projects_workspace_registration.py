from pathlib import Path


def test_projects_panel_exposes_local_directory_registration_form_item_4_3_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    projects_panel_text = (repo_root / "frontend" / "src" / "components" / "ProjectsPanel.tsx").read_text(encoding="utf-8")

    required_snippets = [
        'data-testid="project-register-form"',
        'htmlFor="project-path-input"',
        'id="project-path-input"',
        "Project directory path",
        "event.preventDefault()",
        "onRegisterProject()",
        'type="submit"',
    ]

    for snippet in required_snippets:
        assert snippet in projects_panel_text, f"missing project registration form snippet: {snippet}"


def test_store_validates_local_directory_paths_as_absolute_item_4_3_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    store_text = (repo_root / "frontend" / "src" / "store.ts").read_text(encoding="utf-8")

    required_snippets = [
        "const isAbsoluteProjectPath = (path: string) =>",
        "if (!isAbsoluteProjectPath(normalizedPath)) {",
        "error: 'Project directory path must be absolute.',",
    ]

    for snippet in required_snippets:
        assert snippet in store_text, f"missing absolute local path validation snippet: {snippet}"


def test_checklist_marks_item_4_3_01_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [4.3-01]" in checklist_text
