from pathlib import Path


def test_role_persona_scenarios_doc_exists_with_required_success_criteria() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    doc_path = repo_root / "ui-role-persona-scenarios.md"

    assert doc_path.exists(), "missing role persona scenarios doc for checklist item 3.1-01"

    doc_text = doc_path.read_text(encoding="utf-8")
    required_snippets = [
        "Checklist item: [3.1-01]",
        "ui-spec.md",
        "3.1 User Roles",
        "Pipeline Author Scenario",
        "Operator Scenario",
        "Reviewer/Auditor Scenario",
        "Project Owner/Planner Scenario",
        "Concrete UI Success Criteria",
        "Given",
        "When",
        "Then",
    ]
    for snippet in required_snippets:
        assert snippet in doc_text, f"missing required persona scenario coverage: {snippet}"


