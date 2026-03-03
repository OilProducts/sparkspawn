"""Documentation and spec artifact contracts for UI migration governance."""


# ---- begin tests/integration/test_ui_advanced_feature_access.py ----

from pathlib import Path


def test_advanced_feature_access_doc_exists_with_required_coverage() -> None:
    repo_root = Path(__file__).resolve().parents[3]
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



# ---- end tests/integration/test_ui_advanced_feature_access.py ----


# ---- begin tests/integration/test_ui_parity_complete_user_journey_script.py ----

from pathlib import Path


def test_parity_complete_user_journey_acceptance_script_exists_with_required_coverage() -> None:
    repo_root = Path(__file__).resolve().parents[3]
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



# ---- end tests/integration/test_ui_parity_complete_user_journey_script.py ----


# ---- begin tests/integration/test_ui_parity_risk_report.py ----

from pathlib import Path


def test_parity_risk_report_exists_with_required_failure_mode_coverage() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    report_path = repo_root / "ui-parity-risk-report.md"

    assert report_path.exists(), "missing parity-risk report for checklist item 1.1-02"

    report_text = report_path.read_text(encoding="utf-8")

    required_snippets = [
        "Checklist item: [1.1-02]",
        "Behavior-Loss Failure Modes",
        "Hidden-Config Failure Modes",
        "stack.child_dotfile",
        "tool_hooks.pre",
        "manager.actions",
        "human.default_choice",
        "subgraph",
        "node[...] defaults",
        "edge[...] defaults",
        "Severity",
        "Mitigation direction",
    ]
    for snippet in required_snippets:
        assert snippet in report_text, f"missing required parity-risk coverage: {snippet}"



# ---- end tests/integration/test_ui_parity_risk_report.py ----


# ---- begin tests/integration/test_ui_raw_dot_required_config_report.py ----

from pathlib import Path


def test_raw_dot_required_config_report_exists_with_required_coverage() -> None:
    repo_root = Path(__file__).resolve().parents[3]
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

# ---- end tests/integration/test_ui_raw_dot_required_config_report.py ----


# ---- begin tests/integration/test_ui_role_persona_scenarios.py ----

from pathlib import Path


def test_role_persona_scenarios_doc_exists_with_required_success_criteria() -> None:
    repo_root = Path(__file__).resolve().parents[3]
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



# ---- end tests/integration/test_ui_role_persona_scenarios.py ----


# ---- begin tests/integration/test_ui_runtime_parser_boundaries.py ----

from pathlib import Path


def test_runtime_parser_boundaries_doc_exists_with_required_coverage() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    doc_path = repo_root / "ui-runtime-parser-boundaries.md"

    assert doc_path.exists(), "missing runtime/parser boundaries doc for checklist item 1.3-01"

    doc_text = doc_path.read_text(encoding="utf-8")
    required_snippets = [
        "Checklist item: [1.3-01]",
        "ui-spec.md",
        "attractor-spec.md",
        "Non-Goals",
        "Replacing the DOT runtime parser or executor",
        "UI-owned responsibilities",
        "Runtime/parser-owned responsibilities",
        "Boundary Rules",
        "do not reinterpret execution semantics",
        "no runtime parser changes",
    ]
    for snippet in required_snippets:
        assert snippet in doc_text, f"missing required runtime/parser boundary coverage: {snippet}"



# ---- end tests/integration/test_ui_runtime_parser_boundaries.py ----


# ---- begin tests/integration/test_ui_spec_first_behavior_mapping.py ----

import re
from pathlib import Path


def test_spec_first_behavior_mapping_doc_exists_with_required_control_coverage() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    doc_path = repo_root / "ui-spec-first-behavior-map.md"

    assert doc_path.exists(), "missing spec-first behavior mapping doc for checklist item 2-01"

    doc_text = doc_path.read_text(encoding="utf-8")
    required_snippets = [
        "Checklist item: [2-01]",
        "ui-spec.md",
        "attractor-spec.md",
        "Control-to-Spec Behavior Map",
        "Top navigation mode switch (Editor/Execution/Settings/Runs)",
        "Execute button",
        "Add Node button",
        "Flow create/delete/select controls",
        "Graph settings drawer",
        "Apply To Nodes button",
        "Reset From Global button",
        "Node inspector fields",
        "Node quick-edit controls",
        "Edge inspector fields",
        "Validation panel entries",
        "Canvas controls (pan/zoom/fit/minimap)",
        "Run history refresh/open/cancel actions",
        "Run initiation payload and policy banners",
        "Execution footer cancel control",
        "Execution footer unsupported pause/resume reason",
        "Terminal clear action",
        "Projects workspace controls",
        "Project AI conversation controls",
        "Project spec proposal review controls",
        "Project plan generation controls",
        "Explainability panel controls",
        "Run stream panel controls",
        "Stylesheet editor controls",
        "Subgraph/default block controls",
        "Run checkpoint viewer controls",
        "Run context inspector controls",
        "Run artifact browser controls",
        "Human prompt question-type controls",
        "Grouped multi-question/inform controls",
        "Raw DOT mode toggle and handoff diagnostics",
        "Inspector empty state scaffold",
        "Validation edge diagnostic badge",
        "Human default choice controls",
        "Spec references",
    ]

    for snippet in required_snippets:
        assert snippet in doc_text, f"missing required spec-first mapping coverage: {snippet}"

    required_component_paths = [
        "frontend/src/components/Navbar.tsx",
        "frontend/src/components/Sidebar.tsx",
        "frontend/src/components/Editor.tsx",
        "frontend/src/components/GraphSettings.tsx",
        "frontend/src/components/TaskNode.tsx",
        "frontend/src/components/ValidationPanel.tsx",
        "frontend/src/components/RunsPanel.tsx",
        "frontend/src/components/ExecutionControls.tsx",
        "frontend/src/components/Terminal.tsx",
        "frontend/src/components/SettingsPanel.tsx",
        "frontend/src/components/ProjectsPanel.tsx",
        "frontend/src/components/ExplainabilityPanel.tsx",
        "frontend/src/components/RunStream.tsx",
        "frontend/src/components/StylesheetEditor.tsx",
        "frontend/src/components/InspectorScaffold.tsx",
        "frontend/src/components/ValidationEdge.tsx",
    ]
    for component_path in required_component_paths:
        assert component_path in doc_text, f"missing mapped control coverage for component: {component_path}"

    required_ui_spec_sections = [
        "4.1",
        "4.2",
        "4.3",
        "5.1",
        "5.2",
        "5.3",
        "5.4",
        "5.5",
        "6.1",
        "6.2",
        "6.3",
        "6.4",
        "6.5",
        "6.6",
        "6.7",
        "7.1",
        "7.2",
        "7.3",
        "8.1",
        "8.2",
        "8.3",
        "8.4",
        "8.5",
        "9.1",
        "9.2",
        "9.3",
        "9.4",
        "9.5",
        "9.6",
        "10.1",
        "10.2",
        "10.3",
        "10.4",
    ]
    for section_reference in required_ui_spec_sections:
        pattern = rf"`ui-spec\.md`\s+[^\n|]*\b{re.escape(section_reference)}\b"
        assert re.search(pattern, doc_text), f"missing ui-spec section mapping coverage: {section_reference}"

    # Require a broad mapping table so the checklist item does not pass with a minimal subset.
    map_lines = [line for line in doc_text.splitlines() if line.startswith("| ") and " | " in line]
    assert len(map_lines) >= 30, "control mapping is too narrow for item 2-01"

# ---- end tests/integration/test_ui_spec_first_behavior_mapping.py ----

