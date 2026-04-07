from __future__ import annotations

from pathlib import Path

from attractor.dsl import parse_dot
from attractor.handlers.registry import SHAPE_TO_TYPE
from attractor.dsl.dot_lint import (
    find_dot_paths,
    find_non_canonical_dot_diffs,
    find_start_node_lint_errors,
)


def test_flows_are_canonical_dot() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    starter_flows_dir = repo_root / "src" / "spark" / "starter_flows"
    fixture_flows_dir = repo_root / "tests" / "fixtures" / "flows"
    dot_paths = find_dot_paths(starter_flows_dir) + find_dot_paths(fixture_flows_dir)

    assert dot_paths, "expected at least one .dot file under src/spark/starter_flows/ or tests/fixtures/flows/"
    non_canonical = find_non_canonical_dot_diffs(dot_paths)

    assert not non_canonical, "non-canonical .dot files detected:\n" + "\n".join(non_canonical)


def test_find_dot_paths_recurses_into_subdirectories(tmp_path: Path) -> None:
    top = tmp_path / "top.dot"
    nested = tmp_path / "nested" / "child.dot"
    nested.parent.mkdir(parents=True, exist_ok=True)
    top.write_text("digraph G { a -> b; }\n", encoding="utf-8")
    nested.write_text("digraph G { b -> c; }\n", encoding="utf-8")

    found = find_dot_paths(tmp_path)

    assert found == [nested, top]


def test_lint_reports_start_node_cardinality_violations(tmp_path: Path) -> None:
    missing_start = tmp_path / "missing_start.dot"
    missing_start.write_text(
        "digraph G { task [shape=box]; done [shape=Msquare]; task -> done; }\n",
        encoding="utf-8",
    )

    errors = find_start_node_lint_errors([missing_start])

    assert len(errors) == 1
    assert "start_node" in errors[0]
    assert "exactly one start node" in errors[0]


def test_starter_child_dotfile_references_are_relative_and_resolve_within_starter_flows() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    starter_flows_dir = repo_root / "src" / "spark" / "starter_flows"
    resolved_starter_root = starter_flows_dir.resolve()

    for dot_path in find_dot_paths(starter_flows_dir):
        graph = parse_dot(dot_path.read_text(encoding="utf-8"))
        child_dotfile_attr = graph.graph_attrs.get("stack.child_dotfile")
        if child_dotfile_attr is None:
            continue
        child_dotfile = str(child_dotfile_attr.value).strip()
        if not child_dotfile:
            continue

        child_path = Path(child_dotfile)
        assert not child_path.is_absolute(), f"starter child flow must use a relative path: {dot_path}"

        resolved_child = (dot_path.parent / child_path).resolve()
        assert resolved_child.suffix == ".dot", f"starter child flow must point to a .dot file: {dot_path}"
        assert resolved_child.exists(), f"starter child flow is missing: {resolved_child}"
        try:
            resolved_child.relative_to(resolved_starter_root)
        except ValueError as exc:
            raise AssertionError(
                f"starter child flow must stay within src/spark/starter_flows/: {resolved_child}"
            ) from exc


def test_starter_status_envelope_contracts_only_appear_on_codergen_nodes() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    starter_flows_dir = repo_root / "src" / "spark" / "starter_flows"

    for dot_path in find_dot_paths(starter_flows_dir):
        graph = parse_dot(dot_path.read_text(encoding="utf-8"))
        for node in graph.nodes.values():
            contract = node.attrs.get("codergen.response_contract")
            if contract is None:
                continue

            assert str(contract.value).strip() == "status_envelope", (
                f"unsupported starter response contract in {dot_path}: {node.id}"
            )
            assert _resolved_handler_type(node) == "codergen", (
                f"starter response contract must only be used on codergen nodes: {dot_path}:{node.id}"
            )


def test_starter_json_status_envelope_prompts_opt_into_runtime_contract() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    starter_flows_dir = repo_root / "src" / "spark" / "starter_flows"
    envelope_markers = ("JSON status envelope", "Attractor's status envelope")

    for dot_path in find_dot_paths(starter_flows_dir):
        graph = parse_dot(dot_path.read_text(encoding="utf-8"))
        for node in graph.nodes.values():
            prompt_attr = node.attrs.get("prompt")
            if prompt_attr is None:
                continue

            prompt = str(prompt_attr.value)
            if not any(marker in prompt for marker in envelope_markers):
                continue

            contract = node.attrs.get("codergen.response_contract")
            assert contract is not None, f"starter structured prompt missing response contract: {dot_path}:{node.id}"
            assert str(contract.value).strip() == "status_envelope", (
                f"starter structured prompt has wrong response contract: {dot_path}:{node.id}"
            )


def test_justfile_exposes_dot_lint_recipe() -> None:
    justfile = Path(__file__).resolve().parents[2] / "justfile"
    content = justfile.read_text(encoding="utf-8")

    assert "\ndot-lint:\n" in f"\n{content}"
    assert "uv run pytest -q tests/repo_hygiene/test_dot_format_lint.py" in content


def test_ci_runs_dot_lint() -> None:
    workflows_dir = Path(__file__).resolve().parents[2] / ".github" / "workflows"
    workflow_paths = sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml"))

    assert workflow_paths, "expected at least one CI workflow under .github/workflows/"

    has_dot_lint_step = False
    for path in workflow_paths:
        content = path.read_text(encoding="utf-8")
        if "just dot-lint" in content or "tests/repo_hygiene/test_dot_format_lint.py" in content:
            has_dot_lint_step = True
            break

    assert has_dot_lint_step, "expected CI workflow to run DOT lint check"


def test_ci_runs_parser_unsupported_grammar_regression_suite() -> None:
    justfile = Path(__file__).resolve().parents[2] / "justfile"
    justfile_content = justfile.read_text(encoding="utf-8")

    assert "\nparser-unsupported-grammar:\n" in f"\n{justfile_content}"
    assert "uv run pytest -q tests/dsl/test_parser.py -k unsupported_grammar_regression" in justfile_content

    workflows_dir = Path(__file__).resolve().parents[2] / ".github" / "workflows"
    workflow_paths = sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml"))

    assert workflow_paths, "expected at least one CI workflow under .github/workflows/"

    has_parser_guard_step = False
    for path in workflow_paths:
        content = path.read_text(encoding="utf-8")
        if "just parser-unsupported-grammar" in content:
            has_parser_guard_step = True
            break

    assert has_parser_guard_step, "expected CI workflow to run parser unsupported-grammar regression suite"


def _resolved_handler_type(node) -> str:
    explicit = node.attrs.get("type")
    if explicit is not None:
        explicit_value = str(explicit.value).strip()
        if explicit_value:
            return explicit_value

    shape = node.attrs.get("shape")
    if shape is not None:
        return SHAPE_TO_TYPE.get(str(shape.value).strip(), "codergen")

    return "codergen"
