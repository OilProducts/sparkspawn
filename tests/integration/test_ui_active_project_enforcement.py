from pathlib import Path


def test_store_enforces_active_project_for_editor_and_execution_item_4_2_03() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    store_text = (repo_root / "frontend" / "src" / "store.ts").read_text(encoding="utf-8")

    required_snippets = [
        "const modeRequiresActiveProject = (mode: ViewMode) => mode === 'editor' || mode === 'execution'",
        "const resolveViewModeForProjectScope = (mode: ViewMode, activeProjectPath: string | null): ViewMode => {",
        "return modeRequiresActiveProject(mode) && !activeProjectPath ? 'projects' : mode",
        "const nextViewMode = resolveViewModeForProjectScope(mode, state.activeProjectPath)",
    ]

    for snippet in required_snippets:
        assert snippet in store_text, f"missing active-project mode enforcement snippet: {snippet}"


def test_default_route_state_starts_in_projects_without_active_project_item_4_2_03() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    store_text = (repo_root / "frontend" / "src" / "store.ts").read_text(encoding="utf-8")

    assert "const DEFAULT_ROUTE_STATE: RouteState = {" in store_text
    assert "viewMode: 'projects'," in store_text
    assert "activeProjectPath: null," in store_text


def test_execute_action_requires_active_project_item_4_2_03() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    navbar_text = (repo_root / "frontend" / "src" / "components" / "Navbar.tsx").read_text(encoding="utf-8")

    required_snippets = [
        "if (!activeProjectPath || !activeFlow || hasValidationErrors) return",
        "disabled={!activeProjectPath || !activeFlow || hasValidationErrors}",
    ]

    for snippet in required_snippets:
        assert snippet in navbar_text, f"missing execute active-project guard snippet: {snippet}"


def test_mutating_flow_edits_require_active_project_item_5_4_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    editor_text = (repo_root / "frontend" / "src" / "components" / "Editor.tsx").read_text(encoding="utf-8")
    graph_settings_text = (repo_root / "frontend" / "src" / "components" / "GraphSettings.tsx").read_text(encoding="utf-8")
    sidebar_text = (repo_root / "frontend" / "src" / "components" / "Sidebar.tsx").read_text(encoding="utf-8")
    store_text = (repo_root / "frontend" / "src" / "store.ts").read_text(encoding="utf-8")
    task_node_text = (repo_root / "frontend" / "src" / "components" / "TaskNode.tsx").read_text(encoding="utf-8")

    editor_snippets = [
        "const activeProjectPath = useStore((state) => state.activeProjectPath);",
        "if (!activeProjectPath || !activeFlow) return;",
        "if (activeProjectPath && normalizedContent !== data.content) {",
    ]
    graph_settings_snippets = [
        "const activeProjectPath = useStore((state) => state.activeProjectPath)",
        "if (!activeProjectPath || !activeFlow) return",
    ]
    sidebar_snippets = [
        "const activeProjectPath = useStore((state) => state.activeProjectPath)",
        "if (!activeProjectPath) return",
        "onClick={() => activeProjectPath && setActiveFlow(f)}",
    ]
    store_snippets = [
        "if (!state.activeProjectPath) {",
        "activeFlow: null,",
    ]
    task_node_snippets = [
        "const activeProjectPath = useStore((state) => state.activeProjectPath);",
        "if (!activeProjectPath || !activeFlow) return;",
    ]

    for snippet in editor_snippets:
        assert snippet in editor_text, f"missing editor active-project mutation guard snippet: {snippet}"
    for snippet in graph_settings_snippets:
        assert snippet in graph_settings_text, f"missing graph-settings active-project mutation guard snippet: {snippet}"
    for snippet in sidebar_snippets:
        assert snippet in sidebar_text, f"missing sidebar active-project mutation guard snippet: {snippet}"
    for snippet in store_snippets:
        assert snippet in store_text, f"missing store active-project mutation guard snippet: {snippet}"
    for snippet in task_node_snippets:
        assert snippet in task_node_text, f"missing task-node active-project mutation guard snippet: {snippet}"


