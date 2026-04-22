from __future__ import annotations

import asyncio

import pytest

import unified_llm.agent as agent


async def _next_event(stream) -> agent.SessionEvent:
    return await asyncio.wait_for(anext(stream), timeout=1)


@pytest.mark.asyncio
async def test_check_context_usage_emits_a_warning_when_history_exceeds_the_threshold(
    tmp_path,
) -> None:
    profile = agent.ProviderProfile(
        id="fake-provider",
        model="fake-model",
        context_window_size=100,
    )
    session = agent.Session(
        profile=profile,
        execution_env=agent.LocalExecutionEnvironment(working_dir=tmp_path),
    )
    session.history = [agent.UserTurn(content="x" * 400)]
    stream = session.events()

    start_event = await _next_event(stream)
    assert start_event.kind == agent.EventKind.SESSION_START

    assert agent.check_context_usage(session) is True

    warning_event = await _next_event(stream)
    assert warning_event.kind == agent.EventKind.WARNING
    assert warning_event.data == {"message": "Context usage at ~100% of context window"}


@pytest.mark.asyncio
async def test_check_context_usage_stays_quiet_at_the_80_percent_boundary(tmp_path) -> None:
    profile = agent.ProviderProfile(
        id="fake-provider",
        model="fake-model",
        context_window_size=100,
    )
    session = agent.Session(
        profile=profile,
        execution_env=agent.LocalExecutionEnvironment(working_dir=tmp_path),
    )
    session.history = [agent.UserTurn(content="x" * 320)]
    stream = session.events()

    start_event = await _next_event(stream)
    assert start_event.kind == agent.EventKind.SESSION_START

    assert agent.check_context_usage(session) is False
    assert session.event_queue.empty()
