from tests.contracts.frontend.frontend_behavior_runner import assert_frontend_behavior_contract_passed
from tests.contracts.frontend._support.static_contracts import (
    blend_on_white,
    contrast_ratio,
    hsl_to_rgb,
    parse_root_hsl_token,
    read_frontend_index_css,
)


def test_keyboard_navigation_covers_projects_authoring_and_execution_flows_item_13_1_01() -> None:
    assert_frontend_behavior_contract_passed("13.1.01")


def test_focus_visible_and_semantic_label_audit_across_interactive_controls_item_13_1_02() -> None:
    assert_frontend_behavior_contract_passed("13.1.02")


def test_diagnostic_status_color_contrast_meets_accessibility_thresholds_item_13_1_03() -> None:
    index_css = read_frontend_index_css()
    destructive_token_rgb = hsl_to_rgb(parse_root_hsl_token(index_css, "destructive"))
    white = (255, 255, 255)

    warning_text = (146, 64, 14)
    warning_background_base = (245, 158, 11)
    info_text = (3, 105, 161)
    info_background_base = (14, 165, 233)
    success_text = (22, 101, 52)
    success_background_base = (34, 197, 94)

    samples = (
        ("error text on base surface", contrast_ratio(destructive_token_rgb, white)),
        ("error text on diagnostic badge /10", contrast_ratio(destructive_token_rgb, blend_on_white(destructive_token_rgb, 0.1))),
        ("error text on diagnostic badge /15", contrast_ratio(destructive_token_rgb, blend_on_white(destructive_token_rgb, 0.15))),
        ("error text on status badge /20", contrast_ratio(destructive_token_rgb, blend_on_white(destructive_token_rgb, 0.2))),
        ("warning text on base surface", contrast_ratio(warning_text, white)),
        ("warning text on diagnostic badge /10", contrast_ratio(warning_text, blend_on_white(warning_background_base, 0.1))),
        ("warning text on diagnostic badge /15", contrast_ratio(warning_text, blend_on_white(warning_background_base, 0.15))),
        ("warning text on status badge /20", contrast_ratio(warning_text, blend_on_white(warning_background_base, 0.2))),
        ("info text on base surface", contrast_ratio(info_text, white)),
        ("info text on diagnostic badge /10", contrast_ratio(info_text, blend_on_white(info_background_base, 0.1))),
        ("info text on diagnostic badge /15", contrast_ratio(info_text, blend_on_white(info_background_base, 0.15))),
        ("info text on status badge /20", contrast_ratio(info_text, blend_on_white(info_background_base, 0.2))),
        ("success text on base surface", contrast_ratio(success_text, white)),
        ("success text on status badge /10", contrast_ratio(success_text, blend_on_white(success_background_base, 0.1))),
        ("success text on status badge /15", contrast_ratio(success_text, blend_on_white(success_background_base, 0.15))),
        ("success text on status badge /20", contrast_ratio(success_text, blend_on_white(success_background_base, 0.2))),
    )

    failing_samples = [f"{name}: {ratio:.2f}" for name, ratio in samples if ratio < 4.5]
    assert failing_samples == []


def test_responsive_layout_behavior_for_inspector_timeline_and_diagnostics_item_13_2_01() -> None:
    assert_frontend_behavior_contract_passed("13.2.01")


def test_mobile_narrow_viewport_usability_for_project_and_operational_tasks_item_13_2_02() -> None:
    assert_frontend_behavior_contract_passed("13.2.02")


def test_viewport_regression_contracts_and_smoke_evidence_item_13_2_03() -> None:
    assert_frontend_behavior_contract_passed("13.2.03")


def test_performance_budgets_defined_for_canvas_and_timeline_item_13_3_01() -> None:
    assert_frontend_behavior_contract_passed("13.3.01")


def test_performance_profile_and_optimizations_for_medium_graphs_item_13_3_02() -> None:
    assert_frontend_behavior_contract_passed("13.3.02")


def test_sustained_sse_throughput_stress_item_13_3_03() -> None:
    assert_frontend_behavior_contract_passed("13.3.03")
