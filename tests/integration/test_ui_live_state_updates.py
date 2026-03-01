from __future__ import annotations

from pathlib import Path


def test_run_stream_maps_runtime_stage_events_to_node_status_transitions_item_8_3_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    run_stream_text = (repo_root / "frontend" / "src" / "components" / "RunStream.tsx").read_text(encoding="utf-8")

    assert "const RUNTIME_STAGE_STATUS_MAP: Record<string, 'running' | 'success' | 'failed'> = {" in run_stream_text
    assert "StageStarted: 'running'" in run_stream_text
    assert "StageRetrying: 'running'" in run_stream_text
    assert "StageCompleted: 'success'" in run_stream_text
    assert "StageFailed: 'failed'" in run_stream_text
    assert "const runtimeNodeId = typeof data.node_id === 'string' ? data.node_id : null" in run_stream_text
    assert "const runtimeNodeStatus = RUNTIME_STAGE_STATUS_MAP[data.type]" in run_stream_text
    assert "if (runtimeNodeId && runtimeNodeStatus) {" in run_stream_text
    assert "setNodeStatus(runtimeNodeId, runtimeNodeStatus)" in run_stream_text


def test_checklist_marks_item_8_3_01_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [8.3-01]" in checklist_text
