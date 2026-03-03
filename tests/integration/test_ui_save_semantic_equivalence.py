from __future__ import annotations

from pathlib import Path


def test_ui_no_op_save_paths_enforce_semantic_equivalence_item_5_3_03() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    flow_persistence_text = (repo_root / "frontend" / "src" / "lib" / "flowPersistence.ts").read_text(
        encoding="utf-8"
    )
    editor_text = (repo_root / "frontend" / "src" / "components" / "Editor.tsx").read_text(encoding="utf-8")

    assert "expect_semantic_equivalence" in flow_persistence_text
    assert "status === 'semantic_mismatch'" in flow_persistence_text
    assert "const EXPECT_SEMANTIC_EQUIVALENCE_OPTIONS: SaveFlowOptions = { expectSemanticEquivalence: true }" in (
        flow_persistence_text
    )
    assert "saveFlowContentExpectingSemanticEquivalence" in flow_persistence_text

    assert "saveFlowContentExpectingSemanticEquivalence" in editor_text
    assert "const shouldExpectSemanticEquivalence = nonSelectChanges.length > 0" in editor_text
    assert "scheduleSave(nextNodes, edges, EXPECT_SEMANTIC_EQUIVALENCE_OPTIONS);" in editor_text
    assert "const expectSemanticEquivalence = rawDotEntryDraftRef.current === rawDotDraft;" in editor_text
    assert "const save = expectSemanticEquivalence ? saveFlowContentExpectingSemanticEquivalence : saveFlowContent;" in (
        editor_text
    )


def test_ui_smoke_exercises_runtime_semantic_equivalence_noop_paths_item_5_3_03() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    smoke_text = (repo_root / "frontend" / "e2e" / "ui-smoke.spec.ts").read_text(encoding="utf-8")

    assert "semantic-equivalence save blocks mismatch and confirms no-op round-trip for item 5.3-03" in smoke_text
    assert '"expect_semantic_equivalence":true' in smoke_text
    assert '"status":"semantic_mismatch"' in smoke_text
    assert "raw-dot-handoff-error" in smoke_text
    assert "19a-semantic-equivalence-mismatch-blocked.png" in smoke_text
    assert "19b-semantic-equivalence-round-trip-saved.png" in smoke_text
