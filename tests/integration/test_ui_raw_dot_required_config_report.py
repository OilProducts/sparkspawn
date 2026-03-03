from pathlib import Path


def test_raw_dot_required_config_report_exists_with_required_coverage() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    report_path = repo_root / "ui-raw-dot-required-config.md"

    assert report_path.exists(), "missing required-config raw DOT report for checklist item 1.1-01"

    report_text = report_path.read_text(encoding="utf-8")

    required_snippets = [
        "[1.1-01]",
        "subgraph",
        "node[...] defaults",
        "edge[...] defaults",
        "unknown-valid extension attributes",
        "advanced key/value editor",
        "Current Required Raw-DOT Surfaces",
    ]
    for snippet in required_snippets:
        assert snippet in report_text, f"missing required report coverage: {snippet}"

    no_longer_required_snippets = [
        "stack.child_dotfile",
        "stack.child_workdir",
        "tool_hooks.pre",
        "tool_hooks.post",
        "manager.poll_interval",
        "manager.max_cycles",
        "manager.stop_condition",
        "manager.actions",
        "human.default_choice",
    ]
    for snippet in no_longer_required_snippets:
        assert snippet not in report_text, f"report still marks UI-supported attr as raw-DOT-only: {snippet}"
