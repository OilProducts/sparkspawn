from __future__ import annotations

import asyncio
import re
from pathlib import Path

import attractor.api.server as server


class _DisconnectImmediatelyRequest:
    async def is_disconnected(self) -> bool:
        return True


def _normalized_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


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
