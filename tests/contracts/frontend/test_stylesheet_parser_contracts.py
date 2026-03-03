from __future__ import annotations

import asyncio

import attractor.api.server as server
from tests.contracts.frontend.frontend_behavior_runner import assert_frontend_behavior_test_passed


INVALID_STYLESHEET_FLOW = '''
digraph stylesheet_probe {
    graph [model_stylesheet=".bad$class { llm_model: gpt-5; }"];
    start [label="Start", shape=Mdiamond];
    done [label="Done", shape=Msquare];
    start -> done;
}
'''.strip()

WHITESPACE_STYLESHEET_FLOW = '''
digraph stylesheet_probe_whitespace {
    graph [model_stylesheet="   "];
    start [label="Start", shape=Mdiamond];
    done [label="Done", shape=Msquare];
    start -> done;
}
'''.strip()


def test_graph_settings_exposes_stylesheet_parse_lint_feedback_item_6_5_02() -> None:
    assert_frontend_behavior_test_passed("renders graph settings feedback for stylesheet diagnostics and tool hook warnings")


def test_preview_exposes_stylesheet_syntax_diagnostics_item_6_5_02() -> None:
    payload = asyncio.run(server.preview_pipeline(server.PreviewRequest(flow_content=INVALID_STYLESHEET_FLOW)))
    diagnostics = payload["diagnostics"]

    stylesheet_diags = [diag for diag in diagnostics if diag["rule_id"] == "stylesheet_syntax"]
    assert stylesheet_diags, "invalid stylesheet should surface stylesheet_syntax diagnostics"
    assert any(diag["severity"] == "error" for diag in stylesheet_diags)


def test_preview_exposes_stylesheet_syntax_diagnostics_for_whitespace_stylesheet_item_6_5_02() -> None:
    payload = asyncio.run(server.preview_pipeline(server.PreviewRequest(flow_content=WHITESPACE_STYLESHEET_FLOW)))
    diagnostics = payload["diagnostics"]

    stylesheet_diags = [diag for diag in diagnostics if diag["rule_id"] == "stylesheet_syntax"]
    assert stylesheet_diags, "whitespace stylesheet should surface stylesheet_syntax diagnostics"
    assert any(diag["severity"] == "error" for diag in stylesheet_diags)

