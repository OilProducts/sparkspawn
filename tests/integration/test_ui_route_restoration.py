from pathlib import Path


def test_ui_route_restoration_persists_view_flow_and_run_item_4_03() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    store_path = repo_root / "frontend" / "src" / "store.ts"
    store_text = store_path.read_text(encoding="utf-8")

    required_snippets = [
        'const ROUTE_STATE_STORAGE_KEY = "sparkspawn.ui_route_state"',
        "const loadRouteState = (): RouteState => {",
        "const saveRouteState = (state: RouteState) => {",
        "viewMode: restoredRouteState.viewMode,",
        "activeFlow: restoredRouteState.activeFlow,",
        "selectedRunId: restoredRouteState.selectedRunId,",
        "setViewMode: (mode) =>",
        "setActiveFlow: (flow) =>",
        "setSelectedRunId: (id) =>",
        "saveRouteState(",
    ]

    for snippet in required_snippets:
        assert snippet in store_text, f"missing route restoration behavior: {snippet}"


def test_checklist_marks_item_4_03_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [4-03]" in checklist_text
