from pathlib import Path


def test_store_tracks_recent_and_favorite_projects_for_fast_switching_item_4_3_05() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    store_text = (repo_root / "frontend" / "src" / "store.ts").read_text(encoding="utf-8")

    required_snippets = [
        "isFavorite: boolean",
        "lastAccessedAt: string | null",
        "recentProjectPaths: string[]",
        "toggleProjectFavorite: (projectPath: string) => void",
        "const pushRecentProjectPath = (recentProjectPaths: string[], projectPath: string | null) =>",
        "recentProjectPaths: pushRecentProjectPath(state.recentProjectPaths, projectPath)",
    ]

    for snippet in required_snippets:
        assert snippet in store_text, f"missing recent/favorite switching store snippet: {snippet}"


def test_projects_panel_exposes_favorite_and_recent_project_switching_controls_item_4_3_05() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    projects_panel_text = (repo_root / "frontend" / "src" / "components" / "ProjectsPanel.tsx").read_text(encoding="utf-8")

    required_snippets = [
        "const favoriteProjects = projects.filter((project) => project.isFavorite)",
        "const recentProjects = recentProjectPaths",
        'data-testid="favorite-projects-list"',
        'data-testid="recent-projects-list"',
        'data-testid="favorite-toggle-button"',
        "toggleProjectFavorite(project.directoryPath)",
        "setActiveProjectPath(projectPath)",
    ]

    for snippet in required_snippets:
        assert snippet in projects_panel_text, f"missing recent/favorite switching UI snippet: {snippet}"


def test_checklist_marks_item_4_3_05_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [4.3-05]" in checklist_text
