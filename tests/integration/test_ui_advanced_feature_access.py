from pathlib import Path


def test_advanced_feature_access_doc_exists_with_required_coverage() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    doc_path = repo_root / "ui-advanced-feature-access.md"

    assert doc_path.exists(), "missing advanced feature access guardrail doc for checklist item 1.3-03"

    doc_text = doc_path.read_text(encoding="utf-8")
    required_snippets = [
        "Checklist item: [1.3-03]",
        "ui-spec.md",
        "1.3 Non-Goals",
        "Hiding advanced features in favor of a simplified-only mode",
        "Required controls must remain accessible",
        "Progressive disclosure is allowed",
        "must not remove required spec controls",
        "Verification approach",
    ]
    for snippet in required_snippets:
        assert snippet in doc_text, f"missing required advanced-feature coverage: {snippet}"


def test_checklist_marks_item_1_3_03_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [1.3-03]" in checklist_text
