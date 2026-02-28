from pathlib import Path


def test_store_clears_transient_runtime_context_on_project_switch_item_4_2_05() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    store_text = (repo_root / "frontend" / "src" / "store.ts").read_text(encoding="utf-8")

    required_snippets = [
        "const isProjectSwitch = projectPath !== state.activeProjectPath",
        "runtimeStatus: isProjectSwitch ? 'idle' : state.runtimeStatus,",
        "nodeStatuses: isProjectSwitch ? {} : state.nodeStatuses,",
        "humanGate: isProjectSwitch ? null : state.humanGate,",
        "logs: isProjectSwitch ? [] : state.logs,",
        "selectedNodeId: isProjectSwitch ? null : state.selectedNodeId,",
        "selectedEdgeId: isProjectSwitch ? null : state.selectedEdgeId,",
    ]

    for snippet in required_snippets:
        assert snippet in store_text, f"missing project-switch leakage guard snippet: {snippet}"


def test_run_stream_scopes_status_hydration_to_active_project_item_4_2_05() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    run_stream_text = (repo_root / "frontend" / "src" / "components" / "RunStream.tsx").read_text(encoding="utf-8")

    required_snippets = [
        "const activeProjectPath = useStore((state) => state.activeProjectPath)",
        "const runBelongsToProjectScope = (runWorkingDirectory: string, projectPath: string | null) => {",
        "if (part === '..') {",
        "segments.pop()",
        "const statusRunInScope = runBelongsToProjectScope(lastWorkingDirectory, activeProjectPath)",
        "if (!selectedRunId && runId && statusRunInScope) {",
        "if (!selectedRunId && (!runId || !statusRunInScope)) {",
        "setRuntimeStatus('idle')",
    ]

    for snippet in required_snippets:
        assert snippet in run_stream_text, f"missing run-stream scope-guard snippet: {snippet}"


def test_runs_panel_scope_filter_canonicalizes_parent_path_segments_item_4_2_05() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    runs_panel_text = (repo_root / "frontend" / "src" / "components" / "RunsPanel.tsx").read_text(encoding="utf-8")

    required_snippets = [
        "const normalizeScopePath = (value: string) => {",
        "if (part === '..') {",
        "segments.pop()",
        "return `${prefix}${normalizedBody}`",
    ]

    for snippet in required_snippets:
        assert snippet in runs_panel_text, f"missing runs-panel canonical scope normalization snippet: {snippet}"


def test_checklist_marks_item_4_2_05_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [4.2-05]" in checklist_text
