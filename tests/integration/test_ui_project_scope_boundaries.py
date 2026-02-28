from pathlib import Path


def test_store_tracks_project_scoped_workspace_boundaries_item_4_2_04() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    store_text = (repo_root / "frontend" / "src" / "store.ts").read_text(encoding="utf-8")

    required_snippets = [
        "interface ProjectScopedWorkspace {",
        "conversationId: string | null",
        "specId: string | null",
        "planId: string | null",
        "artifactRunId: string | null",
        "projectScopedWorkspaces: Record<string, ProjectScopedWorkspace>",
        "const DEFAULT_PROJECT_SCOPED_WORKSPACE: ProjectScopedWorkspace = {",
        "const resolveProjectScopedWorkspace = (",
    ]

    for snippet in required_snippets:
        assert snippet in store_text, f"missing project-scoped workspace boundary snippet: {snippet}"


def test_store_restores_project_scoped_flow_run_and_workdir_on_switch_item_4_2_04() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    store_text = (repo_root / "frontend" / "src" / "store.ts").read_text(encoding="utf-8")

    required_snippets = [
        "const currentScope = state.activeProjectPath",
        "const nextProjectScope = projectPath ? resolveProjectScopedWorkspace(nextProjectScopedWorkspaces[projectPath], projectPath) : null",
        "projectScopedWorkspaces: nextProjectScopedWorkspaces,",
        "activeFlow: projectPath ? nextProjectScope.activeFlow : null,",
        "selectedRunId: projectPath ? nextProjectScope.selectedRunId : null,",
        "workingDir: projectPath ? nextProjectScope.workingDir : DEFAULT_WORKING_DIRECTORY,",
    ]

    for snippet in required_snippets:
        assert snippet in store_text, f"missing project-switch scope restoration snippet: {snippet}"


def test_runs_panel_filters_history_to_active_project_scope_item_4_2_04() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    runs_panel_text = (repo_root / "frontend" / "src" / "components" / "RunsPanel.tsx").read_text(encoding="utf-8")

    required_snippets = [
        "const activeProjectPath = useStore((state) => state.activeProjectPath)",
        "const runBelongsToProjectScope = (run: RunRecord, projectPath: string) => {",
        "const scopedRuns = useMemo(() => {",
        "return runs.filter((run) => runBelongsToProjectScope(run, activeProjectPath))",
        "{scopedRuns.length === 0 ? (",
    ]

    for snippet in required_snippets:
        assert snippet in runs_panel_text, f"missing run-history project-scope snippet: {snippet}"


def test_checklist_marks_item_4_2_04_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [4.2-04]" in checklist_text
