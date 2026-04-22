from __future__ import annotations

import json
from importlib import resources

import pytest

import unified_llm


def test_model_catalog_json_matches_the_public_listing() -> None:
    catalog_path = resources.files("unified_llm").joinpath("data/models.json")
    catalog_data = json.loads(catalog_path.read_text(encoding="utf-8"))

    assert isinstance(catalog_data, list)
    assert [entry["id"] for entry in catalog_data] == [
        model.id for model in unified_llm.list_models()
    ]


def test_get_model_info_matches_ids_aliases_and_unknown_models() -> None:
    opus = unified_llm.get_model_info("claude-opus-4-6")
    sonnet = unified_llm.get_model_info("sonnet")
    gemini = unified_llm.get_model_info("gemini-3-pro-preview")

    assert opus is not None
    assert opus.provider == "anthropic"
    assert opus.display_name == "Claude Opus 4.6"
    assert sonnet is not None
    assert sonnet.id == "claude-sonnet-4-5"
    assert gemini is not None
    assert gemini.id == "gemini-3.1-pro-preview"
    assert unified_llm.get_model_info("missing-model") is None


def test_list_models_filters_by_provider_and_returns_a_fresh_list() -> None:
    openai_models = unified_llm.list_models("openai")

    assert [model.id for model in openai_models] == [
        "gpt-5.2",
        "gpt-5.2-mini",
        "gpt-5.2-codex",
    ]

    openai_models.pop()

    assert [model.id for model in unified_llm.list_models("openai")] == [
        "gpt-5.2",
        "gpt-5.2-mini",
        "gpt-5.2-codex",
    ]


@pytest.mark.parametrize(
    ("provider", "capability", "expected_id"),
    [
        ("anthropic", None, "claude-opus-4-6"),
        ("anthropic", "reasoning", "claude-opus-4-6"),
        ("openai", "supports_tools", "gpt-5.2"),
        ("gemini", "vision", "gemini-3.1-pro-preview"),
    ],
)
def test_get_latest_model_prefers_the_first_entry_and_supports_capability_filters(
    provider: str,
    capability: str | None,
    expected_id: str,
) -> None:
    model = unified_llm.get_latest_model(provider, capability)

    assert model is not None
    assert model.id == expected_id


def test_get_latest_model_returns_none_for_unknown_providers() -> None:
    assert unified_llm.get_latest_model("missing-provider") is None


def test_model_info_accepts_alias_iterables_and_validates_types() -> None:
    info = unified_llm.ModelInfo(
        id="custom-model",
        provider="custom",
        display_name="Custom Model",
        context_window=1234,
        max_output=None,
        supports_tools=False,
        supports_vision=True,
        supports_reasoning=False,
        input_cost_per_million=None,
        output_cost_per_million=None,
        aliases=("custom", "custom-model"),
    )

    assert info.aliases == ["custom", "custom-model"]

    with pytest.raises(TypeError):
        unified_llm.ModelInfo(
            id="broken-model",
            provider="custom",
            display_name="Broken Model",
            context_window=1234,
            max_output=None,
            supports_tools="yes",  # type: ignore[arg-type]
            supports_vision=True,
            supports_reasoning=False,
        )
