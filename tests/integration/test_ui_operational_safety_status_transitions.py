from __future__ import annotations

from pathlib import Path


def test_cancel_controls_show_confirmation_and_transition_states_item_2_05() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    execution_controls_path = repo_root / "frontend" / "src" / "components" / "ExecutionControls.tsx"
    runs_panel_path = repo_root / "frontend" / "src" / "components" / "RunsPanel.tsx"

    execution_controls_text = execution_controls_path.read_text(encoding="utf-8")
    runs_panel_text = runs_panel_path.read_text(encoding="utf-8")

    # Destructive/operational action confirmation must be explicit.
    assert "window.confirm('Cancel this run? It will stop after the active node finishes.')" in execution_controls_text
    assert "window.confirm('Cancel this run? It will stop after the active node finishes.')" in runs_panel_text

    # Execution footer should show explicit cancel transition wording.
    assert "const CANCEL_ACTION_LABELS: Record<string, string>" in execution_controls_text
    assert "const transitionHint = TRANSITION_HINTS[runtimeStatus] || null" in execution_controls_text
    assert "Cancel requested. Waiting for active node to finish." in execution_controls_text
    assert "setRuntimeStatus('cancel_requested')" in execution_controls_text
    assert "if (!response.ok)" in execution_controls_text

    # Run history should show clear cancel transition and prevent repeat cancel clicks.
    assert "setRuns((current) =>" in runs_panel_text
    assert "status: 'cancel_requested'" in runs_panel_text
    assert "const canCancel = run.status === 'running'" in runs_panel_text
    assert "const cancelActionLabel = canCancel ? 'Cancel'" in runs_panel_text
    assert "if (!response.ok)" in runs_panel_text


