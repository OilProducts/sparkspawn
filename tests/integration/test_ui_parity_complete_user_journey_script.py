from pathlib import Path


def test_parity_complete_user_journey_acceptance_script_exists_with_required_coverage() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "ui-parity-complete-user-journey.md"

    assert script_path.exists(), "missing parity-complete user journey acceptance script for checklist item 1.2-01"

    script_text = script_path.read_text(encoding="utf-8")

    required_snippets = [
        "Checklist item: [1.2-01]",
        "project-select",
        "author",
        "execute",
        "inspect",
        "without raw DOT fallback",
        "select project -> collaborate on spec -> generate/approve implementation plan -> run build workflows -> inspect outcomes",
        "Preconditions",
        "Acceptance Script",
        "Expected Results",
    ]
    for snippet in required_snippets:
        assert snippet in script_text, f"missing acceptance-script coverage: {snippet}"


