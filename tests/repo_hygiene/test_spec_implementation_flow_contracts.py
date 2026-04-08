from __future__ import annotations

from pathlib import Path

from attractor.dsl import parse_dot


_SPEC_IMPLEMENTATION_DIR = (
    Path(__file__).resolve().parents[2] / "src" / "spark" / "starter_flows" / "spec-implementation"
)


def _load_graph(dot_name: str):
    return parse_dot((_SPEC_IMPLEMENTATION_DIR / dot_name).read_text(encoding="utf-8"))


def _edge_targets(graph):
    return {
        (
            edge.source,
            edge.target,
            str(edge.attrs.get("label").value) if edge.attrs.get("label") is not None else "",
        )
        for edge in graph.edges
    }


def test_spec_implementation_milestone_worker_uses_validation_as_a_real_gate() -> None:
    graph = _load_graph("implement-milestone.dot")

    assert "assess_validation" in graph.nodes
    assert "gate_item_completion" in graph.nodes
    assert "validate_active_item_state" in graph.nodes

    validate_node = graph.nodes["validate_repo"]
    artifact_paths = str(validate_node.attrs["tool.artifacts.paths"].value)
    assert ".specflow/validation-plan.json" in artifact_paths
    assert ".specflow/validation-result.json" not in artifact_paths

    edge_targets = _edge_targets(graph)
    assert ("validate_repo", "assess_validation", "Assess Pass") in edge_targets
    assert ("validate_repo", "assess_validation", "Assess Fail") in edge_targets
    assert ("assess_validation", "review_current", "Review") in edge_targets
    assert ("assess_validation", "implement_current", "Fix Validation") in edge_targets
    assert ("assess_validation", "rewrite_current", "Rewrite Validation") in edge_targets
    assert ("assess_validation", "mark_current_blocked", "Blocked Validation") in edge_targets
    assert ("implement_current", "validate_active_item_state", "Check Item State") in edge_targets
    assert ("validate_active_item_state", "prepare_validation", "Validate") in edge_targets
    assert ("validate_active_item_state", "blocked_exit", "Blocked State") in edge_targets
    assert ("review_current", "gate_item_completion", "Ready To Complete") in edge_targets
    assert ("gate_item_completion", "blocked_exit", "Blocked State") in edge_targets
    assert ("gate_item_completion", "mark_current_done", "Validated") in edge_targets
    assert ("gate_item_completion", "prepare_validation", "Revalidate") in edge_targets
    assert ("mark_current_done", "blocked_exit", "Blocked State") in edge_targets
    assert ("review_current", "mark_current_done", "Done") not in edge_targets
    assert ("implement_current", "prepare_validation", "Validate") not in edge_targets


def test_spec_implementation_milestone_worker_validates_item_queue_before_next_item() -> None:
    graph = _load_graph("implement-milestone.dot")

    assert "validate_item_plan" in graph.nodes

    edge_targets = _edge_targets(graph)
    assert ("extract_items", "validate_item_plan", "") in edge_targets
    assert ("rewrite_current", "validate_item_plan", "") in edge_targets
    assert ("final_milestone_audit", "validate_item_plan", "Extend") in edge_targets
    assert ("validate_item_plan", "next_item", "Validated") in edge_targets
    assert ("validate_item_plan", "extract_items", "Reextract") in edge_targets
    assert ("extract_items", "next_item", "") not in edge_targets
    assert ("rewrite_current", "next_item", "") not in edge_targets
    assert ("final_milestone_audit", "next_item", "Extend") not in edge_targets


def test_spec_implementation_milestone_worker_handles_partial_success_on_status_envelope_judgment_nodes() -> None:
    graph = _load_graph("implement-milestone.dot")

    edge_targets = _edge_targets(graph)
    assert ("assess_validation", "implement_current", "Fix Validation Partial") in edge_targets
    assert ("assess_validation", "mark_current_blocked", "Blocked Validation Partial") in edge_targets
    assert ("assess_validation", "rewrite_current", "Rewrite Validation Partial") in edge_targets
    assert ("blocked_exit", "done", "Finish Partial Blocked") in edge_targets
    assert ("final_milestone_audit", "validate_item_plan", "Extend Partial") in edge_targets
    assert ("final_milestone_audit", "blocked_exit", "Blocked Partial") in edge_targets
    assert ("gate_item_completion", "prepare_validation", "Revalidate Partial") in edge_targets
    assert ("gate_item_completion", "blocked_exit", "Blocked State Partial") in edge_targets
    assert ("next_item", "plan_current", "Work Partial") in edge_targets
    assert ("next_item", "final_milestone_audit", "Audit Partial") in edge_targets
    assert ("next_item", "blocked_exit", "Blocked Partial") in edge_targets
    assert ("review_current", "implement_current", "Fix Partial") in edge_targets
    assert ("review_current", "mark_current_blocked", "Block Partial") in edge_targets
    assert ("review_current", "rewrite_current", "Rewrite Partial") in edge_targets
    assert ("validate_active_item_state", "blocked_exit", "Blocked State Partial") in edge_targets
    assert ("validate_item_plan", "extract_items", "Reextract Partial") in edge_targets


def test_spec_implementation_parent_flow_commits_after_milestone_acceptance() -> None:
    graph = _load_graph("implement-spec.dot")

    assert "commit_milestone" in graph.nodes

    commit_node = graph.nodes["commit_milestone"]
    assert str(commit_node.attrs["shape"].value) == "parallelogram"
    assert "git commit -m" in str(commit_node.attrs["tool.command"].value)

    edge_targets = _edge_targets(graph)
    assert ("audit_milestone", "commit_milestone", "Commit") in edge_targets
    assert ("commit_milestone", "next_milestone", "Continue") in edge_targets
    assert ("commit_milestone", "blocked_exit", "Commit Failed") in edge_targets


def test_spec_implementation_parent_flow_validates_milestone_plan_before_dispatch() -> None:
    graph = _load_graph("implement-spec.dot")

    assert "validate_milestone_plan" in graph.nodes

    edge_targets = _edge_targets(graph)
    assert ("plan_milestones", "validate_milestone_plan", "") in edge_targets
    assert ("rewrite_milestones", "validate_milestone_plan", "") in edge_targets
    assert ("validate_milestone_plan", "next_milestone", "Validated") in edge_targets
    assert ("validate_milestone_plan", "plan_milestones", "Replan") in edge_targets
    assert ("plan_milestones", "next_milestone", "") not in edge_targets
    assert ("rewrite_milestones", "next_milestone", "") not in edge_targets


def test_spec_implementation_parent_flow_handles_partial_success_on_status_envelope_judgment_nodes() -> None:
    graph = _load_graph("implement-spec.dot")

    edge_targets = _edge_targets(graph)
    assert ("audit_milestone", "run_milestone", "Extend") in edge_targets
    assert ("audit_milestone", "blocked_exit", "Blocked Partial") in edge_targets
    assert ("audit_milestone", "rewrite_milestones", "Rewrite Milestones Partial") in edge_targets
    assert ("blocked_exit", "done", "Finish Partial Blocked") in edge_targets
    assert ("evaluate_architecture", "revise_architecture", "Request Partial Rework") in edge_targets
    assert ("evaluate_architecture", "blocked_exit", "Blocked Partial") in edge_targets
    assert ("final_conformance_audit", "plan_milestones", "Extend Partial") in edge_targets
    assert ("final_conformance_audit", "blocked_exit", "Blocked Partial") in edge_targets
    assert ("next_milestone", "run_milestone", "Work Partial") in edge_targets
    assert ("next_milestone", "final_conformance_audit", "Audit Partial") in edge_targets
    assert ("next_milestone", "blocked_exit", "Blocked Partial") in edge_targets
    assert ("repository_integrity_audit", "plan_cleanup_milestone", "Cleanup Partial") in edge_targets
    assert ("repository_integrity_audit", "blocked_exit", "Blocked Partial") in edge_targets
    assert ("validate_milestone_plan", "plan_milestones", "Replan Partial") in edge_targets


def test_spec_implementation_parent_flow_automates_architecture_evaluation() -> None:
    graph = _load_graph("implement-spec.dot")

    assert "evaluate_architecture" in graph.nodes
    assert "review_architecture" not in graph.nodes

    edge_targets = _edge_targets(graph)
    assert ("design_architecture", "evaluate_architecture", "") in edge_targets
    assert ("evaluate_architecture", "plan_milestones", "Approve") in edge_targets
    assert ("evaluate_architecture", "revise_architecture", "Request Rework") in edge_targets
    assert ("evaluate_architecture", "blocked_exit", "Blocked") in edge_targets
    assert ("revise_architecture", "evaluate_architecture", "") in edge_targets


def test_spec_implementation_parent_flow_adds_final_repository_integrity_audit() -> None:
    graph = _load_graph("implement-spec.dot")

    assert "repository_integrity_audit" in graph.nodes
    assert "plan_cleanup_milestone" in graph.nodes

    edge_targets = _edge_targets(graph)
    assert ("final_conformance_audit", "repository_integrity_audit", "Requirements Covered") in edge_targets
    assert ("repository_integrity_audit", "plan_cleanup_milestone", "Cleanup") in edge_targets
    assert ("repository_integrity_audit", "blocked_exit", "Blocked") in edge_targets
    assert ("repository_integrity_audit", "done", "Complete") in edge_targets
    assert ("plan_cleanup_milestone", "validate_milestone_plan", "") in edge_targets
    assert ("audit_milestone", "revise_architecture", "Rework Architecture") not in edge_targets
    assert ("final_conformance_audit", "done", "Complete") not in edge_targets


def test_spec_implementation_flow_uses_gpt_54_for_judgment_heavy_nodes() -> None:
    parent_graph = _load_graph("implement-spec.dot")
    child_graph = _load_graph("implement-milestone.dot")

    assert parent_graph.graph_attrs["ui_default_llm_model"].value == "gpt-5.4-mini"
    assert parent_graph.graph_attrs["ui_default_reasoning_effort"].value == "high"
    assert child_graph.graph_attrs["ui_default_llm_model"].value == "gpt-5.4-mini"
    assert child_graph.graph_attrs["ui_default_reasoning_effort"].value == "high"

    parent_gpt_54_nodes = {
        "extract_requirements",
        "design_architecture",
        "evaluate_architecture",
        "revise_architecture",
        "plan_milestones",
        "validate_milestone_plan",
        "audit_milestone",
        "final_conformance_audit",
        "repository_integrity_audit",
        "plan_cleanup_milestone",
    }
    for node_id in parent_gpt_54_nodes:
        assert parent_graph.nodes[node_id].attrs["llm_model"].value == "gpt-5.4"

    child_gpt_54_nodes = {
        "extract_items",
        "plan_current",
        "prepare_validation",
        "assess_validation",
        "review_current",
        "gate_item_completion",
        "validate_active_item_state",
        "final_milestone_audit",
        "validate_item_plan",
    }
    for node_id in child_gpt_54_nodes:
        assert child_graph.nodes[node_id].attrs["llm_model"].value == "gpt-5.4"

    assert "llm_model" not in parent_graph.nodes["next_milestone"].attrs
    assert "llm_model" not in child_graph.nodes["implement_current"].attrs


def test_spec_implementation_flow_prompts_encode_repository_integrity_rubric() -> None:
    parent_graph = _load_graph("implement-spec.dot")
    child_graph = _load_graph("implement-milestone.dot")

    audit_prompt = str(parent_graph.nodes["audit_milestone"].attrs["prompt"].value)
    assert "honestly deliverable" in audit_prompt
    assert "test-only bootstrap hacks" in audit_prompt
    assert "outcome partial_success with preferred_label Extend" in audit_prompt

    integrity_prompt = str(parent_graph.nodes["repository_integrity_audit"].attrs["prompt"].value)
    assert ".specflow/repository-integrity-gaps.md" in integrity_prompt
    assert "tracked local, generated, cache, or IDE artifacts" in integrity_prompt
    assert "one additional cleanup/refactor milestone" in integrity_prompt

    cleanup_prompt = str(parent_graph.nodes["plan_cleanup_milestone"].attrs["prompt"].value)
    assert "empty requirement_ids list" in cleanup_prompt

    plan_prompt = str(child_graph.nodes["plan_current"].attrs["prompt"].value)
    assert "public bootstrap and installability" in plan_prompt

    implement_prompt = str(child_graph.nodes["implement_current"].attrs["prompt"].value)
    assert "Do not edit milestone_dir/state.json" in implement_prompt
    assert "Do not claim that a later item is now active" in implement_prompt

    prepare_validation_prompt = str(child_graph.nodes["prepare_validation"].attrs["prompt"].value)
    assert "fields item_id, item_title" in prepare_validation_prompt
    assert "ambient tooling" in prepare_validation_prompt
    assert "test-only path hacks" in prepare_validation_prompt
    assert "committed manifests" in prepare_validation_prompt
    assert "Do not edit milestone_dir/state.json or milestone_dir/current-item.json" in prepare_validation_prompt
    assert "Do not write .specflow/validation-result.json" in prepare_validation_prompt

    assess_validation_prompt = str(child_graph.nodes["assess_validation"].attrs["prompt"].value)
    assert "fields item_id, item_title, status" in assess_validation_prompt
    assert "Return outcome success only when" in assess_validation_prompt
    assert "preferred_label Fix" in assess_validation_prompt

    review_prompt = str(child_graph.nodes["review_current"].attrs["prompt"].value)
    assert "Never return outcome success unless" in review_prompt
    assert "item_id matches context.item.id" in review_prompt
    assert "brittle source-text checks" in review_prompt
    assert "duplicate validators" in review_prompt
    assert "mixed-responsibility growth" in review_prompt

    active_item_prompt = str(child_graph.nodes["validate_active_item_state"].attrs["prompt"].value)
    assert "state.json.current_item_id equals context.item.id" in active_item_prompt
    assert "preferred_label Blocked" in active_item_prompt

    validate_item_plan_prompt = str(child_graph.nodes["validate_item_plan"].attrs["prompt"].value)
    assert "at most one item is status=in_progress" in validate_item_plan_prompt
    assert "items with attempts=0 that are already in_progress or completed" in validate_item_plan_prompt

    gate_prompt = str(child_graph.nodes["gate_item_completion"].attrs["prompt"].value)
    assert "state.json.current_item_id" in gate_prompt
    assert "preferred_label Blocked" in gate_prompt
    assert "preferred_label Revalidate" in gate_prompt

    mark_done_prompt = str(child_graph.nodes["mark_current_done"].attrs["prompt"].value)
    assert "Treat context.item.id as the only item" in mark_done_prompt
    assert "Do not modify any other item status" in mark_done_prompt
    assert "preferred_label Blocked" in mark_done_prompt

    final_audit_prompt = str(child_graph.nodes["final_milestone_audit"].attrs["prompt"].value)
    assert "missing deliverability work" in final_audit_prompt

    next_item_prompt = str(child_graph.nodes["next_item"].attrs["prompt"].value)
    assert "cleared context.review.summary" in next_item_prompt
    assert "context.validation.item_id" in next_item_prompt
    assert "missing_prerequisites" in next_item_prompt
