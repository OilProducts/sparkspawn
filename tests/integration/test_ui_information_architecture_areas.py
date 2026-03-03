from pathlib import Path


def test_primary_navigation_exposes_projects_editor_execution_runs_settings_item_4_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    navbar_path = repo_root / "frontend" / "src" / "components" / "Navbar.tsx"
    app_path = repo_root / "frontend" / "src" / "App.tsx"
    store_path = repo_root / "frontend" / "src" / "store.ts"
    shared_types_path = repo_root / "frontend" / "src" / "types.ts"

    navbar_text = navbar_path.read_text(encoding="utf-8")
    app_text = app_path.read_text(encoding="utf-8")
    store_text = store_path.read_text(encoding="utf-8")
    shared_types_text = shared_types_path.read_text(encoding="utf-8")

    assert 'data-testid="nav-mode-projects"' in navbar_text
    assert "Projects" in navbar_text
    assert 'data-testid="nav-mode-editor"' in navbar_text
    assert 'data-testid="nav-mode-execution"' in navbar_text
    assert 'data-testid="nav-mode-runs"' in navbar_text
    assert 'data-testid="nav-mode-settings"' in navbar_text

    assert "viewMode === 'projects'" in app_text
    assert "<ProjectsPanel />" in app_text

    assert "export type ViewMode = 'projects' | 'editor' | 'execution' | 'settings' | 'runs'" in store_text
    assert "export type ViewMode = 'projects' | 'editor' | 'execution' | 'settings' | 'runs';" in shared_types_text


