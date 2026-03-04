from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from attractor.dsl import canonicalize_dot
from tests.contracts.frontend._support.dot_probe import run_canonical_flow_model_probe
from tests.contracts.frontend._support.preview_api import preview_pipeline


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

SPEC_VALID_NO_OP_SAVE_FIXTURES: tuple[str, ...] = (
    "flows/reference-1.1-03-graph-attrs.dot",
    "flows/reference-1.1-03-manager-and-human.dot",
    "tests/fixtures/reference-1.1-03-subgraph-defaults.dot",
    "flows/reference-1.1-03-extension-attrs.dot",
)


def _generate_no_op_save_candidate_from_preview(flow_name: str, flow_content: str) -> str:
    preview_payload = preview_pipeline(flow_content)
    preview_graph = preview_payload["graph"]
    probe_script = """
import { pathToFileURL } from 'node:url'
const mod = await import(pathToFileURL(process.env.CANONICAL_FLOW_MODEL_JS_PATH).href)

const flowName = process.env.CANONICAL_ROUND_TRIP_FLOW_NAME ?? 'fixture.dot'
const previewGraph = JSON.parse(process.env.CANONICAL_ROUND_TRIP_PREVIEW_GRAPH ?? '{}')
const rawDot = process.env.CANONICAL_ROUND_TRIP_RAW_DOT ?? null
const model = mod.buildCanonicalFlowModelFromPreviewGraph(flowName, previewGraph, { rawDot })
const dot = mod.generateDotFromCanonicalFlowModel(flowName, model)
console.log(dot)
""".strip()
    return run_canonical_flow_model_probe(
        probe_script,
        temp_prefix=".tmp-canonical-no-op-save-",
        error_context=f"no-op semantic-equivalence probe for {flow_name}",
        env_extra={
            "CANONICAL_ROUND_TRIP_FLOW_NAME": flow_name,
            "CANONICAL_ROUND_TRIP_PREVIEW_GRAPH": json.dumps(preview_graph),
            "CANONICAL_ROUND_TRIP_RAW_DOT": flow_content,
        },
    )


def test_save_flow_rejects_parse_invalid_dot(
    api_client: TestClient,
    tmp_path: Path,
) -> None:
    target = tmp_path / "flows" / "bad.dot"

    response = api_client.post(
        "/api/flows",
        json={
            "name": "bad.dot",
            "content": INVALID_PARSE_FLOW,
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["status"] == "parse_error"
    assert detail["errors"], "parse failures must return actionable errors"
    assert not target.exists()


def test_save_flow_rejects_validation_error_dot(
    api_client: TestClient,
    tmp_path: Path,
) -> None:
    target = tmp_path / "flows" / "bad.dot"

    response = api_client.post(
        "/api/flows",
        json={
            "name": "bad.dot",
            "content": INVALID_VALIDATION_FLOW,
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["status"] == "validation_error"
    assert detail["diagnostics"], "validation failures must include diagnostics"
    assert detail["errors"], "validation failures must include error diagnostics"
    assert not target.exists()


def test_save_flow_persists_valid_dot(api_client: TestClient, tmp_path: Path) -> None:
    response = api_client.post(
        "/api/flows",
        json={
            "name": "good.dot",
            "content": VALID_FLOW,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "saved"
    assert payload["name"] == "good.dot"
    assert (tmp_path / "flows" / "good.dot").read_text(encoding="utf-8") == canonicalize_dot(
        VALID_FLOW
    )


def test_save_flow_reports_semantic_equivalence_for_no_behavior_change(
    api_client: TestClient,
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

    response = api_client.post(
        "/api/flows",
        json={
            "name": "good.dot",
            "content": VALID_FLOW,
            "expect_semantic_equivalence": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "saved"
    assert payload["semantic_equivalent_to_existing"] is True


def test_save_flow_rejects_semantic_mismatch_when_equivalence_is_expected(
    api_client: TestClient,
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

    response = api_client.post(
        "/api/flows",
        json={
            "name": "good.dot",
            "content": non_equivalent_flow,
            "expect_semantic_equivalence": True,
        },
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["status"] == "semantic_mismatch"
    assert target.read_text(encoding="utf-8") == VALID_FLOW


@pytest.mark.parametrize(
    "fixture_rel_path",
    SPEC_VALID_NO_OP_SAVE_FIXTURES,
    ids=lambda rel_path: Path(rel_path).name,
)
def test_save_flow_no_op_semantic_equivalence_for_spec_valid_fixtures_item_11_2_01(
    api_client: TestClient,
    fixture_rel_path: str,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixture_content = (repo_root / fixture_rel_path).read_text(encoding="utf-8")
    fixture_flow_name = f"fixture-no-op-{Path(fixture_rel_path).stem}.dot"

    seed_response = api_client.post(
        "/api/flows",
        json={
            "name": fixture_flow_name,
            "content": fixture_content,
        },
    )
    assert seed_response.status_code == 200, seed_response.text

    no_op_save_content = _generate_no_op_save_candidate_from_preview(
        fixture_flow_name,
        fixture_content,
    )

    no_op_response = api_client.post(
        "/api/flows",
        json={
            "name": fixture_flow_name,
            "content": no_op_save_content,
            "expect_semantic_equivalence": True,
        },
    )
    assert no_op_response.status_code == 200, no_op_response.text
    no_op_payload = no_op_response.json()
    assert no_op_payload["status"] == "saved"
    assert no_op_payload["semantic_equivalent_to_existing"] is True


def test_flow_endpoints_use_project_root_not_process_cwd(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    unrelated_cwd = tmp_path / "other-cwd"
    unrelated_cwd.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(unrelated_cwd)

    response = api_client.post(
        "/api/flows",
        json={
            "name": "cwd-check.dot",
            "content": VALID_FLOW,
        },
    )
    assert response.status_code == 200

    assert (tmp_path / "flows" / "cwd-check.dot").exists()
    assert not (unrelated_cwd / "flows" / "cwd-check.dot").exists()


def test_get_flow_raises_404_for_missing_flow(api_client: TestClient) -> None:
    response = api_client.get("/api/flows/missing.dot")

    assert response.status_code == 404
    assert response.json()["detail"] == "Flow not found."


def test_delete_flow_deletes_existing_flow_and_raises_404_for_missing(
    api_client: TestClient,
    tmp_path: Path,
) -> None:
    flow_path = tmp_path / "flows" / "delete-me.dot"
    flow_path.parent.mkdir(parents=True, exist_ok=True)
    flow_path.write_text(VALID_FLOW, encoding="utf-8")

    delete_response = api_client.delete("/api/flows/delete-me.dot")
    assert delete_response.status_code == 200
    payload = delete_response.json()
    assert payload == {"status": "deleted"}
    assert not flow_path.exists()

    missing_response = api_client.delete("/api/flows/delete-me.dot")
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "Flow not found."


def test_flow_name_must_be_single_file_name(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/flows",
        json={
            "name": "../escape.dot",
            "content": VALID_FLOW,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Flow name must be a single file name."
