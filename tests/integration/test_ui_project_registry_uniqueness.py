from pathlib import Path


def test_store_defines_project_registry_with_duplicate_path_rejection_item_4_2_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    store_text = (repo_root / "frontend" / "src" / "store.ts").read_text(encoding="utf-8")

    required_snippets = [
        "export interface RegisteredProject {",
        "projectRegistry: Record<string, RegisteredProject>",
        "projectRegistrationError: string | null",
        "registerProject: (directoryPath: string) => ProjectRegistrationResult",
        "const normalizeProjectPath = (path: string) =>",
        "const duplicate = Boolean(state.projectRegistry[normalizedPath])",
        "projectRegistry: {",
        "[normalizedPath]: { directoryPath: normalizedPath },",
        "error: `Project already registered: ${normalizedPath}`",
    ]

    for snippet in required_snippets:
        assert snippet in store_text, f"missing project-registry uniqueness behavior snippet: {snippet}"


def test_projects_panel_exposes_registration_and_duplicate_feedback_item_4_2_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    projects_panel_text = (repo_root / "frontend" / "src" / "components" / "ProjectsPanel.tsx").read_text(encoding="utf-8")

    required_snippets = [
        'data-testid="project-path-input"',
        'data-testid="project-register-button"',
        'data-testid="project-registration-error"',
        'data-testid="project-registry-list"',
        "registerProject(directoryPathInput)",
        "Object.values(projectRegistry)",
    ]

    for snippet in required_snippets:
        assert snippet in projects_panel_text, f"missing project registration UI snippet: {snippet}"


def test_checklist_marks_item_4_2_01_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [4.2-01]" in checklist_text
