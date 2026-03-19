from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.api._support import wait_for_pipeline_completion


def test_pipeline_flow_name_resolves_relative_manager_child_paths_from_parent_flow_dir(
    attractor_api_client: TestClient,
    tmp_path: Path,
) -> None:
    flows_dir = tmp_path / "flows"
    flows_dir.mkdir(parents=True, exist_ok=True)
    (flows_dir / "implementation-worker.dot").write_text(
        """
        digraph implementation_worker {
            start [shape=Mdiamond]
            done [shape=Msquare]

            start -> done
        }
        """,
        encoding="utf-8",
    )
    (flows_dir / "supervised-implementation.dot").write_text(
        """
        digraph supervised_implementation {
            graph [stack.child_dotfile="implementation-worker.dot"]
            done [shape=Msquare]
            manager [shape=house, type="stack.manager_loop", manager.actions=""]
            start [shape=Mdiamond]

            manager -> done [condition="outcome=success"]
            start -> manager
        }
        """,
        encoding="utf-8",
    )
    workdir = tmp_path / "project"
    workdir.mkdir(parents=True, exist_ok=True)

    response = attractor_api_client.post(
        "/pipelines",
        json={
            "flow_name": "supervised-implementation.dot",
            "working_directory": str(workdir),
            "backend": "codex",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "started"

    final_payload = wait_for_pipeline_completion(attractor_api_client, payload["run_id"])

    assert final_payload["status"] == "success"
