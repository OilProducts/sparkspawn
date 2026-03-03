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


@pytest.fixture(autouse=True)
def _isolated_project_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(server, "PROJECT_ROOT", tmp_path)
    return tmp_path


def test_save_flow_rejects_parse_invalid_dot(tmp_path: Path) -> None:
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


def test_save_flow_rejects_validation_error_dot(tmp_path: Path) -> None:
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


def test_save_flow_persists_valid_dot(tmp_path: Path) -> None:
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
    tmp_path: Path,
) -> None:
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
    tmp_path: Path,
) -> None:
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


def test_flow_endpoints_use_project_root_not_process_cwd(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    unrelated_cwd = tmp_path / "other-cwd"
    unrelated_cwd.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(unrelated_cwd)

    asyncio.run(
        server.save_flow(
            server.SaveFlowRequest(
                name="cwd-check.dot",
                content=VALID_FLOW,
            )
        )
    )

    assert (tmp_path / "flows" / "cwd-check.dot").exists()
    assert not (unrelated_cwd / "flows" / "cwd-check.dot").exists()


def test_get_flow_raises_404_for_missing_flow() -> None:
    with pytest.raises(HTTPException, match="Flow not found") as exc:
        asyncio.run(server.get_flow("missing.dot"))

    assert exc.value.status_code == 404


def test_delete_flow_deletes_existing_flow_and_raises_404_for_missing(tmp_path: Path) -> None:
    flow_path = tmp_path / "flows" / "delete-me.dot"
    flow_path.parent.mkdir(parents=True, exist_ok=True)
    flow_path.write_text(VALID_FLOW, encoding="utf-8")

    payload = asyncio.run(server.delete_flow("delete-me.dot"))
    assert payload == {"status": "deleted"}
    assert not flow_path.exists()

    with pytest.raises(HTTPException, match="Flow not found") as exc:
        asyncio.run(server.delete_flow("delete-me.dot"))
    assert exc.value.status_code == 404


def test_flow_name_must_be_single_file_name() -> None:
    with pytest.raises(HTTPException, match="single file name") as exc:
        asyncio.run(
            server.save_flow(
                server.SaveFlowRequest(
                    name="../escape.dot",
                    content=VALID_FLOW,
                )
            )
        )

    assert exc.value.status_code == 400
