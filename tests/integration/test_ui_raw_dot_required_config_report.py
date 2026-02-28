from pathlib import Path


def test_raw_dot_required_config_report_exists_with_required_coverage() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    report_path = repo_root / "ui-raw-dot-required-config.md"

    assert report_path.exists(), "missing required-config raw DOT report for checklist item 1.1-01"

    report_text = report_path.read_text(encoding="utf-8")

    required_snippets = [
        "[1.1-01]",
        "stack.child_dotfile",
        "stack.child_workdir",
        "tool_hooks.pre",
        "tool_hooks.post",
        "manager.poll_interval",
        "manager.max_cycles",
        "manager.stop_condition",
        "manager.actions",
        "human.default_choice",
        "subgraph",
        "node[...] defaults",
        "edge[...] defaults",
    ]
    for snippet in required_snippets:
        assert snippet in report_text, f"missing required report coverage: {snippet}"

    assert "Manager-loop authoring (`house` / `stack.manager_loop`)" not in report_text
    assert "`type` override" in report_text


def test_checklist_marks_item_1_1_01_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [1.1-01]" in checklist_text
