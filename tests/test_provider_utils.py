from __future__ import annotations

import base64
import logging
from pathlib import Path

import pytest

import unified_llm
import unified_llm.provider_utils as provider_utils


def test_extract_provider_options_returns_only_the_selected_provider_copy() -> None:
    request = unified_llm.Request(
        model="gpt-5.2",
        messages=[unified_llm.Message.user("hello")],
        provider_options={
            "openai": {"reasoning": {"effort": "high"}},
            "anthropic": {"beta_headers": ["prompt-caching-2024-07-31"]},
        },
    )

    extracted = provider_utils.extract_provider_options(request, "openai")
    extracted["reasoning"]["effort"] = "low"

    assert extracted == {"reasoning": {"effort": "low"}}
    assert request.provider_options == {
        "openai": {"reasoning": {"effort": "high"}},
        "anthropic": {"beta_headers": ["prompt-caching-2024-07-31"]},
    }
    assert provider_utils.extract_provider_options(request, "missing") == {}
    assert provider_utils.extract_provider_options(None, "openai") == {}


@pytest.mark.parametrize(
    ("provider_options", "selected_provider", "expected_error", "expected_log"),
    [
        (
            ["not", "a", "mapping"],
            "openai",
            "provider_options must be a mapping or None",
            "Unexpected request provider_options type: list",
        ),
        (
            {"openai": ["not", "a", "mapping"]},
            "openai",
            "selected provider options must be a mapping or None",
            "Unexpected provider options type for openai: list",
        ),
    ],
)
def test_extract_provider_options_rejects_invalid_shapes_and_logs(
    caplog: pytest.LogCaptureFixture,
    provider_options: object,
    selected_provider: str,
    expected_error: str,
    expected_log: str,
) -> None:
    request = unified_llm.Request(
        model="gpt-5.2",
        messages=[unified_llm.Message.user("hello")],
        provider_options={"openai": {"reasoning": {"effort": "high"}}},
    )
    request.provider_options = provider_options

    with caplog.at_level(logging.DEBUG, logger="unified_llm.provider_utils.http"):
        with pytest.raises(TypeError, match=expected_error):
            provider_utils.extract_provider_options(request, selected_provider)

    assert any(expected_log in record.message for record in caplog.records)


@pytest.mark.parametrize(
    ("value", "expected_reason", "expected_raw"),
    [
        ("stop", "stop", "stop"),
        ("END_TURN", "stop", "END_TURN"),
        ("max_tokens", "length", "max_tokens"),
        ("tool_use", "tool_calls", "tool_use"),
        ("vendor.custom", "other", "vendor.custom"),
    ],
)
def test_normalize_finish_reason_maps_provider_values(value, expected_reason, expected_raw) -> None:
    finish_reason = provider_utils.normalize_finish_reason(value, provider="anthropic")

    assert finish_reason.reason == expected_reason
    assert finish_reason.raw == expected_raw


def test_normalize_finish_reason_handles_existing_structured_values() -> None:
    finish_reason = provider_utils.normalize_finish_reason(
        unified_llm.FinishReason(reason="stop", raw="end_turn"),
    )

    assert finish_reason.reason == "stop"
    assert finish_reason.raw == "end_turn"


@pytest.mark.parametrize(
    ("provider", "payload", "expected"),
    [
        (
            "openai",
            {
                "usage": {
                    "input_tokens": 12,
                    "output_tokens": 34,
                    "output_tokens_details": {"reasoning_tokens": 9},
                    "input_tokens_details": {"cached_tokens": 4},
                }
            },
            {
                "input_tokens": 12,
                "output_tokens": 34,
                "total_tokens": 46,
                "reasoning_tokens": 9,
                "cache_read_tokens": 4,
                "cache_write_tokens": None,
            },
        ),
        (
            "gemini",
            {
                "usageMetadata": {
                    "promptTokenCount": 21,
                    "candidatesTokenCount": 8,
                    "thoughtsTokenCount": 3,
                    "cachedContentTokenCount": 6,
                }
            },
            {
                "input_tokens": 21,
                "output_tokens": 8,
                "total_tokens": 29,
                "reasoning_tokens": 3,
                "cache_read_tokens": 6,
                "cache_write_tokens": None,
            },
        ),
        (
            "anthropic",
            {
                "usage": {
                    "input_tokens": 11,
                    "output_tokens": 13,
                    "cache_read_input_tokens": 5,
                    "cache_creation_input_tokens": 2,
                }
            },
            {
                "input_tokens": 11,
                "output_tokens": 13,
                "total_tokens": 24,
                "reasoning_tokens": None,
                "cache_read_tokens": 5,
                "cache_write_tokens": 2,
            },
        ),
    ],
)
def test_normalize_usage_maps_provider_specific_fields(provider, payload, expected) -> None:
    usage = provider_utils.normalize_usage(payload, provider=provider)

    assert usage.input_tokens == expected["input_tokens"]
    assert usage.output_tokens == expected["output_tokens"]
    assert usage.total_tokens == expected["total_tokens"]
    assert usage.reasoning_tokens == expected["reasoning_tokens"]
    assert usage.cache_read_tokens == expected["cache_read_tokens"]
    assert usage.cache_write_tokens == expected["cache_write_tokens"]
    assert usage.raw == payload


def test_normalize_warnings_supports_mixed_payloads() -> None:
    warnings = provider_utils.normalize_warnings(
        [
            {"message": "soft limit approached", "code": "rate_limit"},
            "fallback warning",
            unified_llm.Warning(message="already normalized", code=None),
            None,
        ]
    )

    assert warnings == [
        unified_llm.Warning(message="soft limit approached", code="rate_limit"),
        unified_llm.Warning(message="fallback warning", code=None),
        unified_llm.Warning(message="already normalized", code=None),
    ]


def test_normalize_raw_payload_parses_json_and_preserves_plain_text() -> None:
    assert provider_utils.normalize_raw_payload(b'{"ok": true}') == {"ok": True}
    assert provider_utils.normalize_raw_payload('{"kind": "response"}') == {
        "kind": "response"
    }
    assert provider_utils.normalize_raw_payload("  plain text  ") == "plain text"


def test_rate_limit_and_retry_after_helpers_parse_headers() -> None:
    headers = {
        "x-ratelimit-remaining-requests": "9",
        "x-ratelimit-limit-requests": "10",
        "x-ratelimit-remaining-tokens": "100",
        "x-ratelimit-limit-tokens": "200",
        "x-ratelimit-reset": "2026-04-21T00:00:00Z",
        "Retry-After": "12.5",
    }

    rate_limit = provider_utils.normalize_rate_limit(headers)

    assert rate_limit == unified_llm.RateLimitInfo(
        requests_remaining=9,
        requests_limit=10,
        tokens_remaining=100,
        tokens_limit=200,
        reset_at="2026-04-21T00:00:00Z",
    )
    assert provider_utils.parse_retry_after(headers) == 12.5
    assert provider_utils.parse_retry_after("7") == 7.0

    anthropic_headers = {
        "anthropic-ratelimit-requests-remaining": "9",
        "anthropic-ratelimit-requests-limit": "10",
        "anthropic-ratelimit-tokens-remaining": "100",
        "anthropic-ratelimit-tokens-limit": "200",
        "anthropic-ratelimit-requests-reset": "2026-04-21T00:00:00Z",
        "Retry-After": "12.5",
    }

    anthropic_rate_limit = provider_utils.normalize_rate_limit(anthropic_headers)

    assert anthropic_rate_limit == unified_llm.RateLimitInfo(
        requests_remaining=9,
        requests_limit=10,
        tokens_remaining=100,
        tokens_limit=200,
        reset_at="2026-04-21T00:00:00Z",
    )
    assert provider_utils.parse_retry_after(anthropic_headers) == 12.5


def test_normalize_provider_error_preserves_raw_error_body_and_retry_metadata() -> None:
    raw_body = b'{"error": {"message": "slow down", "code": "rate_limit"}}'

    error = provider_utils.normalize_provider_error(
        429,
        provider="openai",
        raw=raw_body,
        headers={"Retry-After": "7"},
    )

    assert isinstance(error, unified_llm.RateLimitError)
    assert error.message == "slow down"
    assert error.provider == "openai"
    assert error.retry_after == 7.0
    assert error.raw == raw_body


@pytest.mark.parametrize(
    "provider",
    [
        "openai",
        "anthropic",
        "gemini",
    ],
)
def test_prepare_image_input_supports_url_bytes_and_local_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    file_path = tmp_path / "diagram.png"
    file_path.write_bytes(b"image-bytes")

    if provider == "openai":
        assert provider_utils.prepare_openai_image_input(
            "https://example.com/image.png",
        ) == "https://example.com/image.png"

        url_value = provider_utils.prepare_image_input(
            str(file_path),
            provider=provider,
        )
        assert isinstance(url_value, str)
        assert url_value.startswith("data:image/png;base64,")
        assert base64.b64decode(url_value.removeprefix("data:image/png;base64,")) == b"image-bytes"

        bytes_value = provider_utils.prepare_openai_image_input(
            b"raw-bytes",
            media_type="image/jpeg",
        )
        assert bytes_value.startswith("data:image/jpeg;base64,")
        assert base64.b64decode(bytes_value.removeprefix("data:image/jpeg;base64,")) == b"raw-bytes"
        return

    if provider == "anthropic":
        source = provider_utils.prepare_anthropic_image_input(file_path)
        assert source == {
            "type": "base64",
            "media_type": "image/png",
            "data": base64.b64encode(b"image-bytes").decode("ascii"),
        }
        assert provider_utils.prepare_anthropic_image_input(
            "https://example.com/image.png",
        ) == {"type": "url", "url": "https://example.com/image.png"}
        assert provider_utils.prepare_anthropic_image_block(file_path) == {
            "type": "image",
            "source": source,
        }
        return

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    home_path = tmp_path / "home-diagram.webp"
    home_path.write_bytes(b"home-bytes")
    home_source = provider_utils.prepare_gemini_image_input("~/home-diagram.webp")
    assert home_source == {
        "data": base64.b64encode(b"home-bytes").decode("ascii"),
        "mimeType": "image/webp",
    }
    assert provider_utils.prepare_gemini_image_block("~/home-diagram.webp") == {
        "inlineData": home_source,
    }
    assert provider_utils.prepare_image_input(
        "./diagram.png",
        provider=provider,
    ) == {
        "data": base64.b64encode(b"image-bytes").decode("ascii"),
        "mimeType": "image/png",
    }


def test_audio_and_document_helpers_translate_when_supported_and_reject_when_not(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"audio-bytes")
    document_path = tmp_path / "report.pdf"
    document_path.write_bytes(b"document-bytes")

    audio = provider_utils.prepare_audio_input(audio_path, provider="anthropic", supported=True)
    document = provider_utils.prepare_document_input(
        document_path,
        provider="anthropic",
        supported=True,
    )

    assert audio == unified_llm.AudioData(data=b"audio-bytes", media_type="audio/mpeg")
    assert document == unified_llm.DocumentData(
        data=b"document-bytes",
        media_type="application/pdf",
        file_name="report.pdf",
    )

    with caplog.at_level("WARNING", logger="unified_llm.provider_utils.media"):
        with pytest.raises(unified_llm.InvalidRequestError, match="audio inputs are not supported"):
            provider_utils.prepare_audio_input(
                audio_path,
                provider="openai",
                supported=False,
            )
    assert any(
        record.name == "unified_llm.provider_utils.media"
        and "does not support audio inputs" in record.message
        for record in caplog.records
    )

    with caplog.at_level("WARNING", logger="unified_llm.provider_utils.media"):
        with pytest.raises(
            unified_llm.InvalidRequestError,
            match="document inputs are not supported",
        ):
            provider_utils.prepare_document_input(
                document_path,
                provider="openai",
                supported=False,
            )
    assert any(
        record.name == "unified_llm.provider_utils.media"
        and "does not support document inputs" in record.message
        for record in caplog.records
    )


def test_package_exports_surface_the_helpers_without_root_import_leakage() -> None:
    assert provider_utils.extract_provider_options is not None
    assert provider_utils.normalize_usage is not None
    assert provider_utils.prepare_image_input is not None
    assert provider_utils.normalize_provider_error is not None
