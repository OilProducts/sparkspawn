from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

import attractor.api.server as server
from attractor.dsl import canonicalize_dot


VALID_FLOW = """
digraph G {
    start [shape=Mdiamond]
    done [shape=Msquare]
    start -> done
}
"""

INVALID_PARSE_FLOW = """
digraph G {
    start [shape=Mdiamond]
    start -> done
"""

INVALID_VALIDATION_FLOW = """
digraph G {
    start [shape=Mdiamond]
    done [shape=Msquare]
    start -> missing
}
"""


def test_save_flow_rejects_parse_invalid_dot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "flows" / "bad.dot"

    with pytest.raises(HTTPException, match="invalid DOT") as exc:
        asyncio.run(
            server.save_flow(
                server.SaveFlowRequest(
                    name="bad.dot",
                    content=INVALID_PARSE_FLOW,
                )
            )
        )

    assert exc.value.status_code == 422
    assert isinstance(exc.value.detail, dict)
    assert exc.value.detail["status"] == "parse_error"
    assert exc.value.detail["errors"], "parse failures must return actionable errors"
    assert not target.exists()


def test_save_flow_rejects_validation_error_dot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "flows" / "bad.dot"

    with pytest.raises(HTTPException, match="validation errors") as exc:
        asyncio.run(
            server.save_flow(
                server.SaveFlowRequest(
                    name="bad.dot",
                    content=INVALID_VALIDATION_FLOW,
                )
            )
        )

    assert exc.value.status_code == 422
    assert isinstance(exc.value.detail, dict)
    assert exc.value.detail["status"] == "validation_error"
    assert exc.value.detail["diagnostics"], "validation failures must include diagnostics"
    assert exc.value.detail["errors"], "validation failures must include error diagnostics"
    assert not target.exists()


def test_save_flow_persists_valid_dot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    payload = asyncio.run(
        server.save_flow(
            server.SaveFlowRequest(
                name="good.dot",
                content=VALID_FLOW,
            )
        )
    )

    assert payload["status"] == "saved"
    assert payload["name"] == "good.dot"
    assert (tmp_path / "flows" / "good.dot").read_text(encoding="utf-8") == canonicalize_dot(
        VALID_FLOW
    )


def test_save_flow_reports_semantic_equivalence_for_no_behavior_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    flows_dir = tmp_path / "flows"
    flows_dir.mkdir(exist_ok=True)
    (flows_dir / "good.dot").write_text(
        """
digraph ExistingFlow {
    done [shape=Msquare]
    start [shape=Mdiamond]
    start -> done
}
""",
        encoding="utf-8",
    )

    payload = asyncio.run(
        server.save_flow(
            server.SaveFlowRequest(
                name="good.dot",
                content=VALID_FLOW,
                expect_semantic_equivalence=True,
            )
        )
    )

    assert payload["status"] == "saved"
    assert payload["semantic_equivalent_to_existing"] is True


def test_save_flow_rejects_semantic_mismatch_when_equivalence_is_expected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    flows_dir = tmp_path / "flows"
    flows_dir.mkdir(exist_ok=True)
    target = flows_dir / "good.dot"
    target.write_text(VALID_FLOW, encoding="utf-8")

    non_equivalent_flow = """
digraph G {
    start [shape=Mdiamond]
    review [shape=box, prompt="Review intermediate output"]
    done [shape=Msquare]
    start -> review
    review -> done
}
"""

    with pytest.raises(HTTPException, match="semantic equivalence") as exc:
        asyncio.run(
            server.save_flow(
                server.SaveFlowRequest(
                    name="good.dot",
                    content=non_equivalent_flow,
                    expect_semantic_equivalence=True,
                )
            )
        )

    assert exc.value.status_code == 409
    assert isinstance(exc.value.detail, dict)
    assert exc.value.detail["status"] == "semantic_mismatch"
    assert target.read_text(encoding="utf-8") == VALID_FLOW
