from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import attractor.api.server as server


class _DisconnectImmediatelyRequest:
    async def is_disconnected(self) -> bool:
        return True


class _DisconnectAfterEventChecksRequest:
    def __init__(self, *, checks: int) -> None:
        self._checks = checks
        self._count = 0

    async def is_disconnected(self) -> bool:
        self._count += 1
        return self._count > self._checks


def _normalized_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def _write_persisted_events(run_id: str, working_directory: Path, events: list[dict]) -> None:
    run_root = server._ensure_run_root_for_project(run_id, str(working_directory))
    events_path = run_root / "events.jsonl"
    with events_path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True) + "\n")


def _decode_event(chunk: str | bytes) -> dict:
    text = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
    lines = [line for line in text.splitlines() if line.startswith("data: ")]
    assert lines
    return json.loads(lines[0].removeprefix("data: "))


async def _collect_stream_events(run_id: str, *, count: int) -> list[dict]:
    response = await server.pipeline_events(
        run_id,
        _DisconnectAfterEventChecksRequest(checks=count),
    )
    iterator = response.body_iterator
    chunks: list[str | bytes] = []
    try:
        for _ in range(count):
            chunks.append(await anext(iterator))
    finally:
        await iterator.aclose()
    return [_decode_event(chunk) for chunk in chunks]


def test_section_95_core_endpoints_are_registered() -> None:
    expected = {
        ("POST", "/pipelines"),
        ("GET", "/pipelines/{}"),
        ("GET", "/pipelines/{}/events"),
        ("POST", "/pipelines/{}/cancel"),
        ("GET", "/pipelines/{}/graph"),
        ("GET", "/pipelines/{}/questions"),
        ("POST", "/pipelines/{}/questions/{}/answer"),
        ("GET", "/pipelines/{}/checkpoint"),
        ("GET", "/pipelines/{}/context"),
    }
    seen: set[tuple[str, str]] = set()
    for route in server.attractor_app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        for method in methods:
            if method in {"GET", "POST"}:
                seen.add((method, _normalized_path(path)))

    assert expected.issubset(seen)


def test_section_95_events_endpoint_uses_sse_headers(
    monkeypatch,
    tmp_path: Path,
) -> None:
    run_id = "run-sse-headers"
    server.configure_runtime_paths(runs_dir=tmp_path / "runs")
    asyncio.run(
        server.EVENT_HUB.publish(run_id, {"type": "runtime", "status": "running", "run_id": run_id})
    )

    response = asyncio.run(server.pipeline_events(run_id, _DisconnectImmediatelyRequest()))

    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers.get("cache-control") == "no-cache"
    assert response.headers.get("connection") == "keep-alive"


def test_section_95_events_endpoint_replays_history_backed_selected_run_events_with_stable_payload(
    monkeypatch,
    tmp_path: Path,
) -> None:
    run_id = "run-section-95-history"
    working_directory = tmp_path / "work"
    server.configure_runtime_paths(runs_dir=tmp_path / "runs")
    _write_persisted_events(
        run_id,
        working_directory,
        [
            {
                "type": "StageCompleted",
                "run_id": run_id,
                "sequence": 1,
                "emitted_at": "2026-04-06T12:00:00Z",
                "node_id": "prepare",
                "index": 1,
                "source_scope": "root",
            },
            {
                "type": "StageStarted",
                "run_id": run_id,
                "sequence": 2,
                "emitted_at": "2026-04-06T12:00:05Z",
                "node_id": "plan_current",
                "index": 2,
                "source_scope": "child",
                "source_parent_node_id": "run_milestone",
                "source_flow_name": "implement-milestone.dot",
            },
        ],
    )
    monkeypatch.setattr(server, "EVENT_HUB", server.PipelineEventHub())

    events = asyncio.run(_collect_stream_events(run_id, count=2))

    assert [event["sequence"] for event in events] == [1, 2]
    assert [event["emitted_at"] for event in events] == [
        "2026-04-06T12:00:00Z",
        "2026-04-06T12:00:05Z",
    ]
    assert events[0]["run_id"] == run_id
    assert events[0]["source_scope"] == "root"
    assert events[1]["source_scope"] == "child"
    assert events[1]["source_parent_node_id"] == "run_milestone"
    assert events[1]["source_flow_name"] == "implement-milestone.dot"


def test_section_95_events_endpoint_preserves_stable_event_identity_across_replay_subscriptions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    run_id = "run-section-95-replay"
    working_directory = tmp_path / "work"
    server.configure_runtime_paths(runs_dir=tmp_path / "runs")
    persisted_events = [
        {
            "type": "StageCompleted",
            "run_id": run_id,
            "sequence": 1,
            "emitted_at": "2026-04-06T12:00:00Z",
            "node_id": "prepare",
            "index": 1,
            "source_scope": "root",
        },
        {
            "type": "StageStarted",
            "run_id": run_id,
            "sequence": 2,
            "emitted_at": "2026-04-06T12:00:05Z",
            "node_id": "plan_current",
            "index": 2,
            "source_scope": "child",
            "source_parent_node_id": "run_milestone",
            "source_flow_name": "implement-milestone.dot",
        },
    ]
    _write_persisted_events(run_id, working_directory, persisted_events)
    monkeypatch.setattr(server, "EVENT_HUB", server.PipelineEventHub())

    first_replay = asyncio.run(_collect_stream_events(run_id, count=2))
    second_replay = asyncio.run(_collect_stream_events(run_id, count=2))

    assert first_replay == second_replay
