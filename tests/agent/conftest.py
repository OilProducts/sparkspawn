from __future__ import annotations

import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live-smoke",
        action="store_true",
        default=False,
        help="run the live provider smoke tests",
    )


def _selection_explicit_for_live_smoke(config: pytest.Config) -> bool:
    if config.getoption("live_smoke"):
        return True

    option = getattr(config, "option", None)
    if option is not None:
        keyword = getattr(option, "keyword", "") or ""
        if "live_smoke" in keyword:
            return True

        markexpr = getattr(option, "markexpr", "") or ""
        if "live_smoke" in markexpr:
            return True

    invocation_params = getattr(config, "invocation_params", None)
    args = getattr(invocation_params, "args", ())
    return any("test_live_smoke.py" in str(argument) for argument in args)


def _missing_live_smoke_credentials() -> list[str]:
    missing = [
        env_name
        for env_name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
        if not os.environ.get(env_name)
    ]
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        missing.append("GEMINI_API_KEY or GOOGLE_API_KEY")
    return missing


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    live_items = [item for item in items if item.get_closest_marker("live_smoke")]
    if not live_items:
        return

    if not _selection_explicit_for_live_smoke(config):
        reason = (
            "live smoke tests are opt-in; use --live-smoke, -m live_smoke, "
            "-k live_smoke, or select tests/agent/test_live_smoke.py directly"
        )
        for item in live_items:
            item.add_marker(pytest.mark.skip(reason=reason))
        return

    missing_credentials = _missing_live_smoke_credentials()
    if missing_credentials:
        reason = "missing live smoke credentials: " + ", ".join(missing_credentials)
        for item in live_items:
            item.add_marker(pytest.mark.skip(reason=reason))
