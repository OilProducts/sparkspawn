from __future__ import annotations

import asyncio
import base64
import copy
import json
import logging

import httpx
import pytest

import unified_llm


def _request_json(request: httpx.Request) -> dict[str, object]:
    return json.loads(request.content.decode("utf-8"))


def _make_complete_transport(
    response_body: dict[str, object],
    *,
    headers: dict[str, str] | None = None,
    status_code: int = 200,
) -> tuple[list[httpx.Request], httpx.MockTransport]:
    captured_requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            status_code,
            headers={"content-type": "application/json", **dict(headers or {})},
            content=json.dumps(response_body).encode("utf-8"),
        )

    return captured_requests, httpx.MockTransport(handler)


def _make_sequenced_complete_transport(
    response_bodies: list[dict[str, object]],
    *,
    headers: dict[str, str] | None = None,
    status_code: int = 200,
) -> tuple[list[httpx.Request], httpx.MockTransport]:
    captured_requests: list[httpx.Request] = []
    queued_bodies = list(response_bodies)

    async def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        if not queued_bodies:
            raise AssertionError("received more Gemini requests than expected")
        response_body = queued_bodies.pop(0)
        return httpx.Response(
            status_code,
            headers={"content-type": "application/json", **dict(headers or {})},
            content=json.dumps(response_body).encode("utf-8"),
        )

    return captured_requests, httpx.MockTransport(handler)


def _make_stream_transport(
    payload: str,
    *,
    headers: dict[str, str] | None = None,
    content_type: str = "text/event-stream",
    status_code: int = 200,
) -> tuple[list[httpx.Request], httpx.MockTransport]:
    captured_requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            status_code,
            headers={"content-type": content_type, **dict(headers or {})},
            content=payload.encode("utf-8"),
        )

    return captured_requests, httpx.MockTransport(handler)


def test_gemini_adapter_is_exposed_through_the_public_adapter_namespace() -> None:
    from unified_llm.adapters import GeminiAdapter as AdapterGeminiAdapter

    assert AdapterGeminiAdapter is unified_llm.GeminiAdapter
    assert AdapterGeminiAdapter.name == "gemini"


def test_gemini_adapter_uses_environment_key_fallback_and_normalizes_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "fallback-key")
    monkeypatch.setenv("GEMINI_BASE_URL", "https://gemini.example/v1")

    adapter = unified_llm.GeminiAdapter()

    assert adapter.api_key == "fallback-key"
    assert adapter.base_url == "https://gemini.example/v1beta"
    assert adapter.config == {
        "api_key": "fallback-key",
        "base_url": "https://gemini.example/v1beta",
    }


@pytest.mark.asyncio
async def test_gemini_adapter_uses_the_native_generate_content_endpoint_and_key_query() -> (
    None
):
    response_body = {
        "responseId": "resp_123",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "text": "Hello",
                        }
                    ],
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 12,
            "candidatesTokenCount": 34,
            "totalTokenCount": 46,
            "thoughtsTokenCount": 5,
            "cachedContentTokenCount": 4,
        },
    }
    captured_requests, transport = _make_complete_transport(
        response_body,
        headers={
            "x-ratelimit-remaining-requests": "7",
            "x-ratelimit-remaining-tokens": "99",
        },
    )
    adapter = unified_llm.GeminiAdapter(
        api_key="explicit-key",
        base_url="https://explicit.example/api/v1",
        timeout=12.5,
        default_headers={
            "X-Custom": "value",
        },
        transport=transport,
    )
    request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[
            unified_llm.Message.system("system instructions"),
            unified_llm.Message.user("hello"),
        ],
    )

    response = await adapter.complete(request)

    assert adapter.api_key == "explicit-key"
    assert adapter.base_url == "https://explicit.example/api/v1beta"
    assert adapter.timeout == 12.5
    assert adapter.default_headers == {"X-Custom": "value"}
    assert len(captured_requests) == 1

    sent_request = captured_requests[0]
    body = _request_json(sent_request)

    assert sent_request.method == "POST"
    assert sent_request.url.path == "/api/v1beta/models/gemini-3.1-pro-preview:generateContent"
    assert sent_request.url.params["key"] == "explicit-key"
    assert "authorization" not in sent_request.headers
    assert sent_request.headers["x-custom"] == "value"
    assert body == {
        "systemInstruction": {
            "parts": [
                {
                    "text": "system instructions",
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": "hello",
                    }
                ],
            }
        ],
    }

    assert response.provider == "gemini"
    assert response.id == "resp_123"
    assert response.model == "gemini-3.1-pro-preview"
    assert response.text == "Hello"
    assert response.finish_reason.reason == "stop"
    assert response.finish_reason.raw == "STOP"
    assert response.usage.input_tokens == 12
    assert response.usage.output_tokens == 34
    assert response.usage.total_tokens == 46
    assert response.usage.reasoning_tokens == 5
    assert response.usage.cache_read_tokens == 4
    assert response.rate_limit is not None
    assert response.rate_limit.requests_remaining == 7
    assert response.rate_limit.tokens_remaining == 99
    assert response.raw == response_body


@pytest.mark.asyncio
async def test_gemini_adapter_parses_thought_parts_tool_calls_and_preserves_signatures(
) -> None:
    first_response_body = {
        "responseId": "resp_thoughts",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "text": "Thinking summary",
                            "thought": True,
                            "thoughtSignature": "sig-think",
                        },
                        {
                            "functionCall": {
                                "name": "lookup_weather",
                                "args": {
                                    "city": "Paris",
                                },
                            },
                            "thoughtSignature": "sig-call",
                        },
                        {
                            "text": "Final answer",
                            "thoughtSignature": "sig-answer",
                        },
                    ],
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 12,
            "candidatesTokenCount": 34,
            "totalTokenCount": 46,
            "thoughtsTokenCount": 5,
            "cachedContentTokenCount": 4,
        },
    }
    final_response_body = {
        "responseId": "resp_followup",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "text": "done",
                        }
                    ],
                },
                "finishReason": "STOP",
            }
        ],
    }
    captured_requests, transport = _make_sequenced_complete_transport(
        [first_response_body, final_response_body],
        headers={
            "x-ratelimit-remaining-requests": "7",
            "x-ratelimit-remaining-tokens": "99",
        },
    )
    adapter = unified_llm.GeminiAdapter(
        api_key="translate-key",
        transport=transport,
    )
    first_request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[
            unified_llm.Message.user("hello"),
        ],
    )

    first_response = await adapter.complete(first_request)

    assert first_response.finish_reason.reason == "tool_calls"
    assert first_response.finish_reason.raw == "STOP"
    assert first_response.text == "Final answer"
    assert first_response.reasoning == "Thinking summary"
    assert first_response.usage.input_tokens == 12
    assert first_response.usage.output_tokens == 34
    assert first_response.usage.total_tokens == 46
    assert first_response.usage.reasoning_tokens == 5
    assert first_response.usage.cache_read_tokens == 4
    assert first_response.rate_limit is not None
    assert first_response.rate_limit.requests_remaining == 7
    assert first_response.rate_limit.tokens_remaining == 99
    assert [part.kind for part in first_response.message.content] == [
        unified_llm.ContentKind.THINKING,
        unified_llm.ContentKind.TOOL_CALL,
        unified_llm.ContentKind.TEXT,
    ]
    assert first_response.message.content[0].thinking is not None
    assert first_response.message.content[0].thinking.signature == "sig-think"
    assert first_response.message.content[1].thinking is None
    assert first_response.message.content[1].provider_metadata == {
        "gemini": {"thoughtSignature": "sig-call"}
    }
    assert first_response.message.content[2].thinking is None
    assert first_response.message.content[2].provider_metadata == {
        "gemini": {"thoughtSignature": "sig-answer"}
    }
    assert len(first_response.tool_calls) == 1
    synthetic_tool_call_id = first_response.tool_calls[0].id
    assert synthetic_tool_call_id.startswith("gemini_call_lookup_weather_")
    assert first_response.tool_calls[0].name == "lookup_weather"
    assert first_response.tool_calls[0].arguments == {"city": "Paris"}
    assert first_response.tool_calls[0].raw_arguments == '{"city":"Paris"}'
    assert len(captured_requests) == 1

    continuation_request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[
            unified_llm.Message.user("hello"),
            first_response.message,
            unified_llm.Message.tool_result(
                synthetic_tool_call_id,
                "72F and sunny",
            ),
        ],
    )

    second_response = await adapter.complete(continuation_request)

    assert len(captured_requests) == 2
    sent_request = captured_requests[1]
    body = _request_json(sent_request)

    assert body == {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": "hello",
                    }
                ],
            },
            {
                "role": "model",
                "parts": [
                    {
                        "text": "Thinking summary",
                        "thought": True,
                        "thoughtSignature": "sig-think",
                    },
                    {
                        "functionCall": {
                            "name": "lookup_weather",
                            "args": {
                                "city": "Paris",
                            },
                        },
                        "thoughtSignature": "sig-call",
                    },
                    {
                        "text": "Final answer",
                        "thoughtSignature": "sig-answer",
                    },
                ],
            },
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "id": synthetic_tool_call_id,
                            "name": "lookup_weather",
                            "response": {
                                "result": "72F and sunny",
                            },
                        }
                    }
                ],
            },
        ]
    }
    assert second_response.text == "done"


@pytest.mark.asyncio
async def test_gemini_adapter_translates_gemini_error_bodies_and_retry_after(
) -> None:
    response_body = {
        "error": {
            "message": "content filter safety block",
            "status": "FAILED_PRECONDITION",
        }
    }
    captured_requests, transport = _make_complete_transport(
        response_body,
        status_code=400,
    )
    adapter = unified_llm.GeminiAdapter(
        api_key="error-key",
        transport=transport,
    )
    request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[unified_llm.Message.user("ping")],
    )

    with pytest.raises(unified_llm.ContentFilterError) as exc_info:
        await adapter.complete(request)

    assert len(captured_requests) == 1
    error = exc_info.value
    assert error.message == "content filter safety block"
    assert error.provider == "gemini"
    assert error.status_code == 400
    assert error.error_code == "FAILED_PRECONDITION"
    assert error.retryable is False
    assert error.retry_after is None
    assert error.raw == response_body


@pytest.mark.asyncio
async def test_gemini_adapter_uses_grpc_code_classification_for_ambiguous_http_400(
) -> None:
    response_body = {
        "error": {
            "message": "slow down",
            "status": "RESOURCE_EXHAUSTED",
        }
    }
    captured_requests, transport = _make_complete_transport(
        response_body,
        headers={"Retry-After": "7"},
        status_code=400,
    )
    adapter = unified_llm.GeminiAdapter(
        api_key="error-key",
        transport=transport,
    )
    request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[unified_llm.Message.user("ping")],
    )

    with pytest.raises(unified_llm.RateLimitError) as exc_info:
        await adapter.complete(request)

    assert len(captured_requests) == 1
    error = exc_info.value
    assert error.message == "slow down"
    assert error.provider == "gemini"
    assert error.status_code == 400
    assert error.error_code == "RESOURCE_EXHAUSTED"
    assert error.retryable is True
    assert error.retry_after == 7.0
    assert error.raw == response_body


@pytest.mark.asyncio
async def test_gemini_adapter_preserves_retry_after_and_grpc_error_metadata(
) -> None:
    response_body = {
        "error": {
            "message": "slow down",
            "status": "RESOURCE_EXHAUSTED",
        }
    }
    captured_requests, transport = _make_complete_transport(
        response_body,
        headers={"Retry-After": "7"},
        status_code=429,
    )
    adapter = unified_llm.GeminiAdapter(
        api_key="error-key",
        transport=transport,
    )
    request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[unified_llm.Message.user("ping")],
    )

    with pytest.raises(unified_llm.RateLimitError) as exc_info:
        await adapter.complete(request)

    assert len(captured_requests) == 1
    error = exc_info.value
    assert error.message == "slow down"
    assert error.provider == "gemini"
    assert error.status_code == 429
    assert error.error_code == "RESOURCE_EXHAUSTED"
    assert error.retryable is True
    assert error.retry_after == 7.0
    assert error.raw == response_body


@pytest.mark.asyncio
async def test_gemini_adapter_translates_system_developer_and_content_parts_into_native_parts(
    ) -> None:
    image_bytes = b"image-bytes"
    response_body = {
        "responseId": "resp_456",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "text": "ok",
                        }
                    ],
                },
            }
        ],
    }
    captured_requests, transport = _make_complete_transport(response_body)
    adapter = unified_llm.GeminiAdapter(
        api_key="translate-key",
        base_url="https://gemini.example/v1",
        transport=transport,
    )
    request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[
            unified_llm.Message.system("system instructions"),
            unified_llm.Message(
                role=unified_llm.Role.DEVELOPER,
                content=[
                    unified_llm.ContentPart(
                        kind=unified_llm.ContentKind.TEXT,
                        text="developer instructions",
                    )
                ],
            ),
            unified_llm.Message.user(
                [
                    unified_llm.ContentPart(
                        kind=unified_llm.ContentKind.TEXT,
                        text="hello",
                    ),
                    unified_llm.ContentPart(
                        kind=unified_llm.ContentKind.IMAGE,
                        image=unified_llm.ImageData(
                            url="https://example.test/image.png",
                        ),
                    ),
                    unified_llm.ContentPart(
                        kind=unified_llm.ContentKind.IMAGE,
                        image=unified_llm.ImageData(
                            data=image_bytes,
                            media_type="image/png",
                        ),
                    ),
                ],
            ),
            unified_llm.Message(
                role=unified_llm.Role.ASSISTANT,
                content=[
                    unified_llm.ContentPart(
                        kind=unified_llm.ContentKind.TEXT,
                        text="assistant turn",
                    ),
                    unified_llm.ContentPart(
                        kind=unified_llm.ContentKind.TOOL_CALL,
                        tool_call=unified_llm.ToolCallData(
                            id="call_123",
                            name="lookup_weather",
                            arguments={"city": "Paris"},
                        ),
                    ),
                ],
            ),
            unified_llm.Message.tool_result(
                "call_123",
                "72F and sunny",
            ),
        ],
    )

    response = await adapter.complete(request)

    assert len(captured_requests) == 1
    sent_request = captured_requests[0]
    body = _request_json(sent_request)
    expected_image_data = base64.b64encode(image_bytes).decode("ascii")

    assert sent_request.url.params["key"] == "translate-key"
    assert body == {
        "systemInstruction": {
            "parts": [
                {
                    "text": "system instructions\n\ndeveloper instructions",
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": "hello",
                    },
                    {
                        "fileData": {
                            "fileUri": "https://example.test/image.png",
                            "mimeType": "image/png",
                        }
                    },
                    {
                        "inlineData": {
                            "data": expected_image_data,
                            "mimeType": "image/png",
                        }
                    },
                ],
            },
            {
                "role": "model",
                "parts": [
                    {
                        "text": "assistant turn",
                    },
                    {
                        "functionCall": {
                            "name": "lookup_weather",
                            "args": {
                                "city": "Paris",
                            },
                        }
                    },
                ],
            },
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "id": "call_123",
                            "name": "lookup_weather",
                            "response": {
                                "result": "72F and sunny",
                            },
                        }
                    }
                ],
            },
        ],
    }
    assert response.text == "ok"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_choice", "expected_tool_config"),
    [
        (
            unified_llm.ToolChoice.auto(),
            {
                "functionCallingConfig": {
                    "mode": "AUTO",
                }
            },
        ),
        (
            unified_llm.ToolChoice.none(),
            {
                "functionCallingConfig": {
                    "mode": "NONE",
                }
            },
        ),
        (
            unified_llm.ToolChoice.required(),
            {
                "functionCallingConfig": {
                    "mode": "ANY",
                }
            },
        ),
        (
            unified_llm.ToolChoice.named("lookup_weather"),
            {
                "functionCallingConfig": {
                    "mode": "ANY",
                    "allowedFunctionNames": ["lookup_weather"],
                }
            },
        ),
    ],
)
async def test_gemini_adapter_serializes_function_declarations_and_tool_choice_config(
    tool_choice: unified_llm.ToolChoice,
    expected_tool_config: dict[str, object],
) -> None:
    response_body = {
        "responseId": "resp_tool_config",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "text": "ok",
                        }
                    ],
                },
            }
        ],
    }
    schema = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
            }
        },
        "required": ["city"],
    }
    time_schema = {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
            }
        },
        "required": ["timezone"],
    }
    captured_requests, transport = _make_complete_transport(response_body)
    adapter = unified_llm.GeminiAdapter(
        api_key="translate-key",
        transport=transport,
    )
    request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[
            unified_llm.Message.user("hello"),
        ],
        tools=[
            unified_llm.Tool.passive(
                name="lookup_weather",
                description="Lookup weather for a city",
                parameters=schema,
            ),
            unified_llm.Tool.passive(
                name="lookup_time",
                description="Lookup time for a city",
                parameters=time_schema,
            ),
        ],
        tool_choice=tool_choice,
        provider_options={
            "anthropic": {
                "tool_choice": {
                    "type": "none",
                }
            },
            "openai_compatible": {
                "tool_choice": "required",
            },
        },
    )

    response = await adapter.complete(request)

    assert len(captured_requests) == 1
    body = _request_json(captured_requests[0])
    assert body == {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": "hello",
                    }
                ],
            }
        ],
        "tools": [
            {
                "functionDeclarations": [
                    {
                        "name": "lookup_weather",
                        "description": "Lookup weather for a city",
                        "parametersJsonSchema": schema,
                    },
                    {
                        "name": "lookup_time",
                        "description": "Lookup time for a city",
                        "parametersJsonSchema": time_schema,
                    },
                ]
            }
        ],
        "toolConfig": expected_tool_config,
    }
    assert response.text == "ok"


@pytest.mark.asyncio
async def test_gemini_adapter_merges_only_gemini_provider_options_into_generation_config(
) -> None:
    response_body = {
        "responseId": "resp_gemini_options",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "text": "ok",
                        }
                    ],
                },
            }
        ],
    }
    structured_schema = {
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
            }
        },
        "required": ["answer"],
        "additionalProperties": False,
    }
    gemini_provider_options = {
        "safetySettings": [
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_ONLY_HIGH",
            }
        ],
        "groundingConfig": {
            "enabled": True,
        },
        "cachedContent": "cachedContents/session-123",
        "temperature": 0.25,
        "thinkingConfig": {
            "includeThoughts": True,
        },
        "responseMimeType": "application/json",
        "responseSchema": structured_schema,
        "structured_output": {
            "provider": "gemini",
            "strategy": "responseSchema",
            "schema": structured_schema,
            "responseMimeType": "application/json",
        },
    }
    provider_options = {
        "openai": {
            "reasoning": {
                "effort": "high",
            }
        },
        "anthropic": {
            "beta_headers": [
                "prompt-caching-2024-07-31",
            ]
        },
        "openai_compatible": {
            "parallel_tool_calls": False,
        },
        "gemini": gemini_provider_options,
    }
    original_provider_options = copy.deepcopy(provider_options)
    captured_requests, transport = _make_complete_transport(response_body)
    adapter = unified_llm.GeminiAdapter(
        api_key="translate-key",
        transport=transport,
    )
    request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[
            unified_llm.Message.user("return json"),
        ],
        provider_options=provider_options,
    )

    response = await adapter.complete(request)

    assert len(captured_requests) == 1
    body = _request_json(captured_requests[0])
    assert body == {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": "return json",
                    }
                ],
            }
        ],
        "safetySettings": [
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_ONLY_HIGH",
            }
        ],
        "groundingConfig": {
            "enabled": True,
        },
        "cachedContent": "cachedContents/session-123",
        "generationConfig": {
            "temperature": 0.25,
            "thinkingConfig": {
                "includeThoughts": True,
            },
            "responseMimeType": "application/json",
            "responseSchema": structured_schema,
        },
    }
    assert request.provider_options == original_provider_options
    assert response.text == "ok"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("gemini_request", "match"),
    [
        (
            unified_llm.Request(
                model="gemini-3.1-pro-preview",
                messages=[
                    unified_llm.Message.user("hello"),
                ],
                tool_choice=unified_llm.ToolChoice.required(),
            ),
            "required requires at least one tool",
        ),
        (
            unified_llm.Request(
                model="gemini-3.1-pro-preview",
                messages=[
                    unified_llm.Message.user("hello"),
                ],
                tools=[
                    unified_llm.Tool.passive(
                        name="lookup_weather",
                        description="Lookup weather for a city",
                        parameters={
                            "type": "object",
                            "properties": {
                                "city": {
                                    "type": "string",
                                }
                            },
                            "required": ["city"],
                        },
                    )
                ],
                tool_choice=unified_llm.ToolChoice.named("lookup_time"),
            ),
            "requires a matching tool",
        ),
    ],
)
async def test_gemini_adapter_rejects_unsupported_tool_choice_requests(
    gemini_request: unified_llm.Request,
    match: str,
) -> None:
    captured_requests, transport = _make_complete_transport(
        {
            "responseId": "resp_unsupported",
            "modelVersion": "gemini-3.1-pro-preview",
            "candidates": [],
        }
    )
    adapter = unified_llm.GeminiAdapter(
        api_key="translate-key",
        transport=transport,
    )

    with pytest.raises(unified_llm.UnsupportedToolChoiceError, match=match):
        await adapter.complete(gemini_request)

    assert captured_requests == []


def test_gemini_adapter_reports_supported_tool_choice_modes() -> None:
    adapter = unified_llm.GeminiAdapter(
        api_key="translate-key",
        client=object(),
    )

    assert adapter.supports_tool_choice("auto") is True
    assert adapter.supports_tool_choice("none") is True
    assert adapter.supports_tool_choice("required") is True
    assert adapter.supports_tool_choice("named") is True
    assert adapter.supports_tool_choice("unsupported") is False


@pytest.mark.asyncio
async def test_gemini_adapter_uses_adapter_state_for_provider_tool_call_ids() -> None:
    first_response_body = {
        "responseId": "resp_tool_call",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "functionCall": {
                                "id": "provider-call-weather-123",
                                "name": "lookup_weather",
                                "args": {
                                    "city": "Paris",
                                },
                            }
                        }
                    ],
                },
            }
        ],
    }
    second_response_body = {
        "responseId": "resp_tool_result",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "text": "done",
                        }
                    ],
                }
            }
        ],
    }
    captured_requests, transport = _make_sequenced_complete_transport(
        [first_response_body, second_response_body]
    )
    adapter = unified_llm.GeminiAdapter(
        api_key="translate-key",
        transport=transport,
    )
    first_request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[unified_llm.Message.user("hello")],
    )

    first_response = await adapter.complete(first_request)
    assert len(first_response.tool_calls) == 1
    provider_tool_call_id = first_response.tool_calls[0].id
    assert first_response.tool_calls[0].name == "lookup_weather"
    assert provider_tool_call_id == "provider-call-weather-123"

    second_request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[
            unified_llm.Message.tool_result(
                provider_tool_call_id,
                "72F and sunny",
            )
        ],
    )

    second_response = await adapter.complete(second_request)

    assert len(captured_requests) == 2
    second_body = _request_json(captured_requests[1])
    assert second_body == {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "id": provider_tool_call_id,
                            "name": "lookup_weather",
                            "response": {
                                "result": "72F and sunny",
                            },
                        }
                    }
                ],
            }
        ]
    }
    assert second_response.text == "done"


@pytest.mark.asyncio
async def test_gemini_adapter_translates_synthetic_tool_call_ids_without_cached_state(
) -> None:
    captured_requests, transport = _make_complete_transport(
        {
            "responseId": "resp_tool_result",
            "modelVersion": "gemini-3.1-pro-preview",
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "text": "done",
                            }
                        ],
                    }
                }
            ],
        }
    )
    adapter = unified_llm.GeminiAdapter(
        api_key="translate-key",
        transport=transport,
    )
    synthetic_tool_call_id = "gemini_call_lookup_weather_0123456789abcdef0123456789abcdef"
    request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[
            unified_llm.Message.tool_result(
                synthetic_tool_call_id,
                "72F and sunny",
            )
        ],
    )

    response = await adapter.complete(request)

    assert len(captured_requests) == 1
    body = _request_json(captured_requests[0])
    assert body == {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "id": synthetic_tool_call_id,
                            "name": "lookup_weather",
                            "response": {
                                "result": "72F and sunny",
                            },
                        }
                    }
                ],
            }
        ]
    }
    assert response.text == "done"


@pytest.mark.asyncio
async def test_gemini_adapter_uses_unique_synthetic_ids_for_concurrent_continuations() -> (
    None
):
    response_bodies = [
        {
            "responseId": "resp_lookup_weather",
            "modelVersion": "gemini-3.1-pro-preview",
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "lookup_weather",
                                    "args": {
                                        "city": "Paris",
                                    },
                                }
                            }
                        ],
                    },
                }
            ],
        },
        {
            "responseId": "resp_lookup_time",
            "modelVersion": "gemini-3.1-pro-preview",
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "lookup_time",
                                    "args": {
                                        "city": "Paris",
                                    },
                                }
                            }
                        ],
                    },
                }
            ],
        },
        {
            "responseId": "resp_weather_done",
            "modelVersion": "gemini-3.1-pro-preview",
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "text": "weather done",
                            }
                        ],
                    }
                }
            ],
        },
        {
            "responseId": "resp_time_done",
            "modelVersion": "gemini-3.1-pro-preview",
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "text": "time done",
                            }
                        ],
                    }
                }
            ],
        },
    ]
    captured_requests: list[httpx.Request] = []
    first_request_started = asyncio.Event()
    second_request_started = asyncio.Event()
    release_first_response = asyncio.Event()
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_index = call_count
        call_count += 1
        captured_requests.append(request)

        if call_index >= len(response_bodies):
            raise AssertionError("received more Gemini requests than expected")

        if call_index == 0:
            first_request_started.set()
            await release_first_response.wait()
        elif call_index == 1:
            second_request_started.set()

        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=json.dumps(response_bodies[call_index]).encode("utf-8"),
        )

    adapter = unified_llm.GeminiAdapter(
        api_key="translate-key",
        transport=httpx.MockTransport(handler),
    )
    first_request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[unified_llm.Message.user("weather please")],
    )
    second_request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[unified_llm.Message.user("time please")],
    )

    first_task = asyncio.create_task(adapter.complete(first_request))
    await first_request_started.wait()
    second_task = asyncio.create_task(adapter.complete(second_request))
    await second_request_started.wait()
    release_first_response.set()

    first_response, second_response = await asyncio.gather(first_task, second_task)
    first_tool_call_id = first_response.tool_calls[0].id
    second_tool_call_id = second_response.tool_calls[0].id

    assert first_response.tool_calls[0].name == "lookup_weather"
    assert second_response.tool_calls[0].name == "lookup_time"
    assert first_tool_call_id != second_tool_call_id
    assert first_tool_call_id.startswith("gemini_call_lookup_weather_")
    assert second_tool_call_id.startswith("gemini_call_lookup_time_")

    weather_continuation = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[
            unified_llm.Message.tool_result(
                first_tool_call_id,
                "72F and sunny",
            )
        ],
    )
    time_continuation = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[
            unified_llm.Message.tool_result(
                second_tool_call_id,
                "3 PM",
            )
        ],
    )

    weather_response = await adapter.complete(weather_continuation)
    time_response = await adapter.complete(time_continuation)

    assert len(captured_requests) == 4
    weather_body = _request_json(captured_requests[2])
    time_body = _request_json(captured_requests[3])
    assert weather_body == {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "id": first_tool_call_id,
                            "name": "lookup_weather",
                            "response": {
                                "result": "72F and sunny",
                            },
                        }
                    }
                ],
            }
        ]
    }
    assert time_body == {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "id": second_tool_call_id,
                            "name": "lookup_time",
                            "response": {
                                "result": "3 PM",
                            },
                        }
                    }
                ],
            }
        ]
    }
    assert weather_response.text == "weather done"
    assert time_response.text == "time done"


@pytest.mark.asyncio
async def test_gemini_adapter_rejects_tool_results_without_a_known_function_name() -> None:
    captured_requests, transport = _make_complete_transport(
        {
            "responseId": "resp_missing",
            "modelVersion": "gemini-3.1-pro-preview",
            "candidates": [],
        }
    )
    adapter = unified_llm.GeminiAdapter(
        api_key="translate-key",
        transport=transport,
    )
    request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[
            unified_llm.Message.tool_result(
                "call_missing",
                "oops",
            )
        ],
    )

    with pytest.raises(
        unified_llm.InvalidRequestError,
        match="known function name for tool_call_id 'call_missing'",
    ) as exc_info:
        await adapter.complete(request)

    assert exc_info.value.provider == "gemini"

    assert captured_requests == []


@pytest.mark.asyncio
async def test_gemini_adapter_rejects_malformed_tool_call_arguments_and_logs_the_parse_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    captured_requests, transport = _make_complete_transport(
        {
            "responseId": "resp_bad_args",
            "modelVersion": "gemini-3.1-pro-preview",
            "candidates": [],
        }
    )
    adapter = unified_llm.GeminiAdapter(
        api_key="translate-key",
        transport=transport,
    )
    request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[
            unified_llm.Message(
                role=unified_llm.Role.ASSISTANT,
                content=[
                    unified_llm.ContentPart(
                        kind=unified_llm.ContentKind.TOOL_CALL,
                        tool_call=unified_llm.ToolCallData(
                            id="call_123",
                            name="lookup_weather",
                            arguments='{"city": "Par',
                        ),
                    )
                ],
            )
        ],
    )

    with caplog.at_level(logging.ERROR, logger="unified_llm.provider_utils.gemini"):
        with pytest.raises(
            unified_llm.InvalidRequestError,
            match="valid JSON object data",
        ):
            await adapter.complete(request)

    assert captured_requests == []
    assert any(
        record.name == "unified_llm.provider_utils.gemini"
        and "Failed to parse Gemini tool_call arguments" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_gemini_adapter_stream_uses_the_native_stream_endpoint_with_alt_sse() -> (
    None
):
    first_stream_chunk = {
        "responseId": "resp_456",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "text": "Streaming",
                        }
                    ],
                },
            }
        ],
    }
    second_stream_chunk = {
        "responseId": "resp_456",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "text": "Streaming hello",
                        }
                    ],
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 1,
            "candidatesTokenCount": 2,
            "totalTokenCount": 3,
        },
    }
    stream_payload = (
        f"data: {json.dumps(first_stream_chunk, separators=(',', ':'), sort_keys=True)}\n\n"
        f"data: {json.dumps(second_stream_chunk, separators=(',', ':'), sort_keys=True)}\n\n"
    )
    captured_requests, transport = _make_stream_transport(stream_payload)
    adapter = unified_llm.GeminiAdapter(
        api_key="stream-key",
        base_url="https://gemini.example/v1",
        transport=transport,
    )
    request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[unified_llm.Message.user("hello")],
    )

    events = [event async for event in adapter.stream(request)]

    assert len(captured_requests) == 1
    sent_request = captured_requests[0]
    assert sent_request.method == "POST"
    assert sent_request.url.path == "/v1beta/models/gemini-3.1-pro-preview:streamGenerateContent"
    assert sent_request.url.params["key"] == "stream-key"
    assert sent_request.url.params["alt"] == "sse"
    assert "authorization" not in sent_request.headers
    assert _request_json(sent_request) == {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": "hello",
                    }
                ],
            }
        ]
    }
    assert [event.type for event in events] == [
        unified_llm.StreamEventType.STREAM_START,
        unified_llm.StreamEventType.TEXT_START,
        unified_llm.StreamEventType.TEXT_DELTA,
        unified_llm.StreamEventType.TEXT_DELTA,
        unified_llm.StreamEventType.TEXT_END,
        unified_llm.StreamEventType.FINISH,
    ]
    assert events[1].delta is None
    assert events[2].delta == "Streaming"
    assert events[3].delta == " hello"
    assert events[-1].response is not None
    assert events[-1].response.text == "Streaming hello"
    assert events[-1].response.raw == [first_stream_chunk, second_stream_chunk]
    assert events[-1].usage is not None
    assert events[-1].usage.input_tokens == 1
    assert events[-1].usage.output_tokens == 2
    assert events[-1].usage.total_tokens == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("second_chunk_text", "expected_text"),
    [
        (" world", "Hello world"),
        ("\nworld", "Hello\nworld"),
    ],
)
async def test_gemini_adapter_stream_preserves_incremental_text_chunks_with_leading_whitespace(
    second_chunk_text: str,
    expected_text: str,
) -> None:
    first_stream_chunk = {
        "responseId": "resp_incremental_text",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "text": "Hello",
                        }
                    ],
                },
            }
        ],
    }
    second_stream_chunk = {
        "responseId": "resp_incremental_text",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "text": second_chunk_text,
                        }
                    ],
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 1,
            "candidatesTokenCount": 2,
            "totalTokenCount": 3,
        },
    }
    stream_payload = (
        f"{json.dumps(first_stream_chunk, separators=(',', ':'), sort_keys=True)}\n"
        f"{json.dumps(second_stream_chunk, separators=(',', ':'), sort_keys=True)}\n"
    )
    captured_requests, transport = _make_stream_transport(
        stream_payload,
        content_type="application/json",
    )
    adapter = unified_llm.GeminiAdapter(
        api_key="stream-key",
        base_url="https://gemini.example/v1",
        transport=transport,
    )
    request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[unified_llm.Message.user("hello")],
    )

    events = [event async for event in adapter.stream(request)]
    accumulator = unified_llm.StreamAccumulator.from_events(events)
    response = accumulator.response

    assert len(captured_requests) == 1
    sent_request = captured_requests[0]
    assert sent_request.method == "POST"
    assert sent_request.url.path == "/v1beta/models/gemini-3.1-pro-preview:streamGenerateContent"
    assert sent_request.url.params["key"] == "stream-key"
    assert sent_request.url.params["alt"] == "sse"
    assert _request_json(sent_request) == {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": "hello",
                    }
                ],
            }
        ]
    }
    assert [event.type for event in events] == [
        unified_llm.StreamEventType.STREAM_START,
        unified_llm.StreamEventType.TEXT_START,
        unified_llm.StreamEventType.TEXT_DELTA,
        unified_llm.StreamEventType.TEXT_DELTA,
        unified_llm.StreamEventType.TEXT_END,
        unified_llm.StreamEventType.FINISH,
    ]
    assert events[2].delta == "Hello"
    assert events[3].delta == second_chunk_text
    assert events[4].delta == expected_text
    assert events[-1].response is not None
    assert events[-1].response.text == expected_text
    assert events[-1].response.raw == [first_stream_chunk, second_stream_chunk]
    assert events[-1].response.finish_reason.reason == "stop"
    assert events[-1].response.finish_reason.raw == "STOP"
    assert events[-1].usage is not None
    assert events[-1].usage.input_tokens == 1
    assert events[-1].usage.output_tokens == 2
    assert events[-1].usage.total_tokens == 3
    assert accumulator.finish_event is not None
    assert accumulator.finish_event.type == unified_llm.StreamEventType.FINISH
    assert accumulator.response.text == expected_text
    assert accumulator.response.raw == [first_stream_chunk, second_stream_chunk]
    assert response.text == expected_text
    assert response.raw == [first_stream_chunk, second_stream_chunk]


@pytest.mark.asyncio
async def test_gemini_adapter_stream_accepts_newline_delimited_json_chunks_and_tool_calls(
) -> None:
    first_stream_chunk = {
        "responseId": "resp_ndjson_tool_call",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "text": "Let me check",
                        }
                    ],
                },
            }
        ],
    }
    second_stream_chunk = {
        "responseId": "resp_ndjson_tool_call",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "functionCall": {
                                "name": "lookup_weather",
                                "args": {
                                    "city": "Paris",
                                },
                            }
                        }
                    ],
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 2,
            "candidatesTokenCount": 4,
            "totalTokenCount": 6,
        },
    }
    payload = (
        f"{json.dumps(first_stream_chunk, separators=(',', ':'), sort_keys=True)}\n"
        f"{json.dumps(second_stream_chunk, separators=(',', ':'), sort_keys=True)}\n"
    )
    captured_requests, transport = _make_stream_transport(
        payload,
        content_type="application/json",
    )
    adapter = unified_llm.GeminiAdapter(
        api_key="stream-key",
        transport=transport,
    )
    request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[unified_llm.Message.user("hello")],
    )

    events: list[unified_llm.StreamEvent] = []
    async for event in adapter.stream(request):
        events.append(event)
        if event.type == unified_llm.StreamEventType.FINISH:
            break
    accumulator = unified_llm.StreamAccumulator.from_events(events)
    response = accumulator.response

    assert len(captured_requests) == 1
    sent_request = captured_requests[0]
    assert sent_request.method == "POST"
    assert sent_request.url.path == "/v1beta/models/gemini-3.1-pro-preview:streamGenerateContent"
    assert sent_request.url.params["key"] == "stream-key"
    assert sent_request.url.params["alt"] == "sse"
    assert _request_json(sent_request) == {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": "hello",
                    }
                ],
            }
        ]
    }
    assert [event.type for event in events] == [
        unified_llm.StreamEventType.STREAM_START,
        unified_llm.StreamEventType.TEXT_START,
        unified_llm.StreamEventType.TEXT_DELTA,
        unified_llm.StreamEventType.TEXT_END,
        unified_llm.StreamEventType.TOOL_CALL_START,
        unified_llm.StreamEventType.TOOL_CALL_END,
        unified_llm.StreamEventType.FINISH,
    ]
    assert events[4].tool_call is not None
    assert events[4].tool_call.id.startswith("gemini_call_lookup_weather_")
    assert events[5].tool_call is not None
    assert events[5].tool_call.id == events[4].tool_call.id
    assert response.text == "Let me check"
    assert response.finish_reason.reason == "tool_calls"
    assert response.finish_reason.raw == "STOP"
    assert response.usage.input_tokens == 2
    assert response.usage.output_tokens == 4
    assert response.usage.total_tokens == 6
    assert response.raw == [first_stream_chunk, second_stream_chunk]
    assert response.tool_calls == [
        unified_llm.ToolCall(
            id=events[4].tool_call.id,
            name="lookup_weather",
            arguments={"city": "Paris"},
            raw_arguments='{"city":"Paris"}',
            type="function",
        )
    ]


@pytest.mark.asyncio
async def test_gemini_adapter_logs_and_converts_malformed_stream_payloads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    first_stream_chunk = {
        "responseId": "resp_stream_error",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "text": "Hel",
                        }
                    ],
                },
            }
        ],
    }
    payload = (
        f"data: {json.dumps(first_stream_chunk, separators=(',', ':'), sort_keys=True)}\n\n"
        "not-json\n"
    )
    captured_requests, transport = _make_stream_transport(payload)
    adapter = unified_llm.GeminiAdapter(
        api_key="stream-key",
        transport=transport,
    )
    request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[unified_llm.Message.user("hello")],
    )

    with caplog.at_level(logging.ERROR, logger="unified_llm.provider_utils.gemini"):
        events = [event async for event in adapter.stream(request)]

    accumulator = unified_llm.StreamAccumulator.from_events(events)

    assert len(captured_requests) == 1
    assert [event.type for event in events] == [
        unified_llm.StreamEventType.STREAM_START,
        unified_llm.StreamEventType.TEXT_START,
        unified_llm.StreamEventType.TEXT_DELTA,
        unified_llm.StreamEventType.ERROR,
    ]
    assert events[-1].error is not None
    assert events[-1].error.provider == "gemini"
    assert events[-1].raw == "not-json"
    assert accumulator.response.text == "Hel"
    assert accumulator.response.finish_reason.reason == "error"
    assert accumulator.finish_event is not None
    assert accumulator.finish_event.type == unified_llm.StreamEventType.ERROR
    assert any(
        record.name == "unified_llm.provider_utils.gemini"
        and "Gemini stream payload" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_gemini_adapter_stream_emits_tool_call_start_and_end_events() -> None:
    stream_payload = (
        'data: {"responseId":"resp_stream_tool_call","modelVersion":"gemini-3.1-pro-preview",'
        '"candidates":[{"content":{"role":"model","parts":[{"functionCall":{"name":"lookup_weather",'
        '"args":{"city":"Paris"}}}]},"finishReason":"STOP"}]}\n\n'
    )
    captured_requests, transport = _make_stream_transport(stream_payload)
    adapter = unified_llm.GeminiAdapter(
        api_key="stream-key",
        base_url="https://gemini.example/v1",
        transport=transport,
    )
    request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[unified_llm.Message.user("hello")],
    )

    events: list[unified_llm.StreamEvent] = []
    async for event in adapter.stream(request):
        events.append(event)
        if event.type == unified_llm.StreamEventType.FINISH:
            break
    accumulator = unified_llm.StreamAccumulator.from_events(events)
    response = accumulator.response

    assert len(captured_requests) == 1
    sent_request = captured_requests[0]
    assert sent_request.method == "POST"
    assert sent_request.url.path == "/v1beta/models/gemini-3.1-pro-preview:streamGenerateContent"
    assert sent_request.url.params["key"] == "stream-key"
    assert sent_request.url.params["alt"] == "sse"
    assert "authorization" not in sent_request.headers
    assert _request_json(sent_request) == {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": "hello",
                    }
                ],
            }
        ]
    }
    assert [event.type for event in events] == [
        unified_llm.StreamEventType.STREAM_START,
        unified_llm.StreamEventType.TOOL_CALL_START,
        unified_llm.StreamEventType.TOOL_CALL_END,
        unified_llm.StreamEventType.FINISH,
    ]
    assert events[1].tool_call is not None
    assert events[1].tool_call.id.startswith("gemini_call_lookup_weather_")
    assert events[2].tool_call is not None
    assert events[2].tool_call.id == events[1].tool_call.id
    assert events[-1].response is not None
    assert events[-1].response.raw == {
        "responseId": "resp_stream_tool_call",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "functionCall": {
                                "name": "lookup_weather",
                                "args": {
                                    "city": "Paris",
                                },
                            }
                        }
                    ],
                },
                "finishReason": "STOP",
            }
        ],
    }
    assert response.finish_reason.reason == "tool_calls"
    assert response.finish_reason.raw == "STOP"
    assert response.tool_calls == [
        unified_llm.ToolCall(
            id=events[1].tool_call.id,
            name="lookup_weather",
            arguments={"city": "Paris"},
            raw_arguments='{"city":"Paris"}',
            type="function",
        )
    ]


@pytest.mark.asyncio
async def test_gemini_adapter_stream_skips_repeated_duplicate_function_call_chunks(
) -> None:
    first_stream_chunk = {
        "responseId": "resp_stream_duplicate_tool_calls",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "functionCall": {
                                "name": "lookup_weather",
                                "args": {
                                    "city": "Paris",
                                },
                            }
                        },
                        {
                            "functionCall": {
                                "name": "lookup_weather",
                                "args": {
                                    "city": "Paris",
                                },
                            }
                        },
                    ],
                },
            }
        ],
    }
    second_stream_chunk = {
        "responseId": "resp_stream_duplicate_tool_calls",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "functionCall": {
                                "name": "lookup_weather",
                                "args": {
                                    "city": "Paris",
                                },
                            }
                        },
                        {
                            "functionCall": {
                                "name": "lookup_weather",
                                "args": {
                                    "city": "Paris",
                                },
                            }
                        },
                    ],
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 2,
            "candidatesTokenCount": 4,
            "totalTokenCount": 6,
        },
    }
    stream_payload = (
        f"data: {json.dumps(first_stream_chunk, separators=(',', ':'), sort_keys=True)}\n\n"
        f"data: {json.dumps(second_stream_chunk, separators=(',', ':'), sort_keys=True)}\n\n"
    )
    captured_requests, transport = _make_stream_transport(stream_payload)
    adapter = unified_llm.GeminiAdapter(
        api_key="stream-key",
        base_url="https://gemini.example/v1",
        transport=transport,
    )
    request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[unified_llm.Message.user("hello")],
    )

    events = [event async for event in adapter.stream(request)]
    accumulator = unified_llm.StreamAccumulator.from_events(events)
    response = accumulator.response

    assert len(captured_requests) == 1
    sent_request = captured_requests[0]
    assert sent_request.method == "POST"
    assert sent_request.url.path == "/v1beta/models/gemini-3.1-pro-preview:streamGenerateContent"
    assert sent_request.url.params["key"] == "stream-key"
    assert sent_request.url.params["alt"] == "sse"
    assert "authorization" not in sent_request.headers
    assert _request_json(sent_request) == {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": "hello",
                    }
                ],
            }
        ]
    }
    assert [event.type for event in events] == [
        unified_llm.StreamEventType.STREAM_START,
        unified_llm.StreamEventType.TOOL_CALL_START,
        unified_llm.StreamEventType.TOOL_CALL_END,
        unified_llm.StreamEventType.TOOL_CALL_START,
        unified_llm.StreamEventType.TOOL_CALL_END,
        unified_llm.StreamEventType.FINISH,
    ]
    assert events[1].tool_call is not None
    assert events[2].tool_call is not None
    assert events[3].tool_call is not None
    assert events[4].tool_call is not None
    assert events[1].tool_call.name == "lookup_weather"
    assert events[3].tool_call.name == "lookup_weather"
    assert events[1].tool_call.id != events[3].tool_call.id
    assert events[1].tool_call.raw_arguments == '{"city":"Paris"}'
    assert events[3].tool_call.raw_arguments == '{"city":"Paris"}'
    assert events[-1].response is not None
    assert response.text == ""
    assert response.finish_reason.reason == "tool_calls"
    assert response.finish_reason.raw == "STOP"
    assert response.usage.input_tokens == 2
    assert response.usage.output_tokens == 4
    assert response.usage.total_tokens == 6
    assert response.raw == [first_stream_chunk, second_stream_chunk]
    assert [tool_call.name for tool_call in response.tool_calls] == [
        "lookup_weather",
        "lookup_weather",
    ]
    assert response.tool_calls[0].id != response.tool_calls[1].id
    assert response.tool_calls[0].raw_arguments == '{"city":"Paris"}'
    assert response.tool_calls[1].raw_arguments == '{"city":"Paris"}'


@pytest.mark.asyncio
async def test_gemini_adapter_stream_preserves_earlier_function_calls_for_continuations() -> (
    None
):
    first_stream_chunk = {
        "responseId": "resp_stream_tool_call",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "functionCall": {
                                "name": "lookup_weather",
                                "args": {
                                    "city": "Paris",
                                },
                            }
                        }
                    ],
                },
            }
        ],
    }
    second_stream_chunk = {
        "responseId": "resp_stream_done",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [],
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 1,
            "candidatesTokenCount": 2,
            "totalTokenCount": 3,
        },
    }
    continuation_response = {
        "responseId": "resp_stream_continuation",
        "modelVersion": "gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "text": "done",
                        }
                    ],
                },
                "finishReason": "STOP",
            }
        ],
    }
    stream_payload = (
        f"data: {json.dumps(first_stream_chunk)}\n\n"
        f"data: {json.dumps(second_stream_chunk)}\n\n"
    )
    captured_requests: list[httpx.Request] = []
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_index = call_count
        call_count += 1
        captured_requests.append(request)

        if call_index == 0:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=stream_payload.encode("utf-8"),
            )

        if call_index == 1:
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                content=json.dumps(continuation_response).encode("utf-8"),
            )

        raise AssertionError("received more Gemini requests than expected")

    adapter = unified_llm.GeminiAdapter(
        api_key="stream-key",
        transport=httpx.MockTransport(handler),
    )
    request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[unified_llm.Message.user("hello")],
    )

    events: list[unified_llm.StreamEvent] = []
    async for event in adapter.stream(request):
        events.append(event)
        if event.type == unified_llm.StreamEventType.FINISH:
            break
    accumulator = unified_llm.StreamAccumulator.from_events(events)
    response = accumulator.response

    assert len(captured_requests) == 1
    sent_request = captured_requests[0]
    assert sent_request.method == "POST"
    assert sent_request.url.path == "/v1beta/models/gemini-3.1-pro-preview:streamGenerateContent"
    assert sent_request.url.params["alt"] == "sse"
    assert _request_json(sent_request) == {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": "hello",
                    }
                ],
            }
        ]
    }
    assert [event.type for event in events] == [
        unified_llm.StreamEventType.STREAM_START,
        unified_llm.StreamEventType.TOOL_CALL_START,
        unified_llm.StreamEventType.TOOL_CALL_END,
        unified_llm.StreamEventType.FINISH,
    ]
    assert events[1].tool_call is not None
    assert events[2].tool_call is not None
    assert events[1].tool_call.id == events[2].tool_call.id
    assert response.finish_reason.reason == "tool_calls"
    assert response.finish_reason.raw == "STOP"
    assert response.usage.input_tokens == 1
    assert response.usage.output_tokens == 2
    assert response.usage.total_tokens == 3
    assert response.tool_calls == [
        unified_llm.ToolCall(
            id=response.tool_calls[0].id,
            name="lookup_weather",
            arguments={"city": "Paris"},
            raw_arguments='{"city":"Paris"}',
            type="function",
        )
    ]
    synthetic_tool_call_id = response.tool_calls[0].id
    assert synthetic_tool_call_id.startswith("gemini_call_lookup_weather_")

    continuation = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[
            unified_llm.Message.tool_result(
                synthetic_tool_call_id,
                "72F and sunny",
            )
        ],
    )

    continuation_response = await adapter.complete(continuation)

    assert len(captured_requests) == 2
    continuation_body = _request_json(captured_requests[1])
    assert continuation_body == {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "id": synthetic_tool_call_id,
                            "name": "lookup_weather",
                            "response": {
                                "result": "72F and sunny",
                            },
                        }
                    }
                ],
            }
        ]
    }
    assert continuation_response.text == "done"


@pytest.mark.asyncio
async def test_gemini_adapter_streams_unique_synthetic_ids_and_keeps_concurrent_mappings() -> (
    None
):
    first_stream_chunks = [
        {
            "responseId": "resp_stream_weather_call",
            "modelVersion": "gemini-3.1-pro-preview",
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "lookup_weather",
                                    "args": {
                                        "city": "Paris",
                                    },
                                }
                            }
                        ],
                    },
                }
            ],
        },
        {
            "responseId": "resp_stream_weather_done",
            "modelVersion": "gemini-3.1-pro-preview",
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [],
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 1,
                "candidatesTokenCount": 2,
                "totalTokenCount": 3,
            },
        },
    ]
    second_stream_chunks = [
        {
            "responseId": "resp_stream_time_call",
            "modelVersion": "gemini-3.1-pro-preview",
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "lookup_time",
                                    "args": {
                                        "city": "Paris",
                                    },
                                }
                            }
                        ],
                    },
                }
            ],
        },
        {
            "responseId": "resp_stream_time_done",
            "modelVersion": "gemini-3.1-pro-preview",
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [],
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 1,
                "candidatesTokenCount": 2,
                "totalTokenCount": 3,
            },
        },
    ]
    continuation_bodies = [
        {
            "responseId": "resp_stream_weather_continuation",
            "modelVersion": "gemini-3.1-pro-preview",
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "text": "weather done",
                            }
                        ],
                    },
                    "finishReason": "STOP",
                }
            ],
        },
        {
            "responseId": "resp_stream_time_continuation",
            "modelVersion": "gemini-3.1-pro-preview",
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "text": "time done",
                            }
                        ],
                    },
                    "finishReason": "STOP",
                }
            ],
        },
    ]
    captured_requests: list[httpx.Request] = []
    first_request_started = asyncio.Event()
    second_request_started = asyncio.Event()
    release_first_response = asyncio.Event()
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_index = call_count
        call_count += 1
        captured_requests.append(request)

        if call_index == 0:
            first_request_started.set()
            await release_first_response.wait()
            payload = "".join(
                f"data: {json.dumps(chunk)}\n\n" for chunk in first_stream_chunks
            )
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=payload.encode("utf-8"),
            )

        if call_index == 1:
            second_request_started.set()
            payload = "".join(
                f"data: {json.dumps(chunk)}\n\n" for chunk in second_stream_chunks
            )
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=payload.encode("utf-8"),
            )

        if call_index in (2, 3):
            body = continuation_bodies[call_index - 2]
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                content=json.dumps(body).encode("utf-8"),
            )

        raise AssertionError("received more Gemini requests than expected")

    adapter = unified_llm.GeminiAdapter(
        api_key="stream-key",
        transport=httpx.MockTransport(handler),
    )
    first_request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[unified_llm.Message.user("weather please")],
    )
    second_request = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[unified_llm.Message.user("time please")],
    )

    async def collect_events(
        request: unified_llm.Request,
    ) -> list[unified_llm.StreamEvent]:
        return [event async for event in adapter.stream(request)]

    first_task = asyncio.create_task(collect_events(first_request))
    await first_request_started.wait()
    second_task = asyncio.create_task(collect_events(second_request))
    await second_request_started.wait()
    release_first_response.set()

    first_events, second_events = await asyncio.gather(first_task, second_task)
    first_response = first_events[-1].response
    second_response = second_events[-1].response

    assert first_response is not None
    assert second_response is not None
    assert first_response.tool_calls[0].name == "lookup_weather"
    assert second_response.tool_calls[0].name == "lookup_time"
    assert first_response.tool_calls[0].id != second_response.tool_calls[0].id
    assert first_response.tool_calls[0].id.startswith("gemini_call_lookup_weather_")
    assert second_response.tool_calls[0].id.startswith("gemini_call_lookup_time_")

    weather_continuation = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[
            unified_llm.Message.tool_result(
                first_response.tool_calls[0].id,
                "72F and sunny",
            )
        ],
    )
    time_continuation = unified_llm.Request(
        model="gemini-3.1-pro-preview",
        messages=[
            unified_llm.Message.tool_result(
                second_response.tool_calls[0].id,
                "3 PM",
            )
        ],
    )

    weather_response = await adapter.complete(weather_continuation)
    time_response = await adapter.complete(time_continuation)

    assert len(captured_requests) == 4
    weather_body = _request_json(captured_requests[2])
    time_body = _request_json(captured_requests[3])
    assert weather_body == {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "id": first_response.tool_calls[0].id,
                            "name": "lookup_weather",
                            "response": {
                                "result": "72F and sunny",
                            },
                        }
                    }
                ],
            }
        ]
    }
    assert time_body == {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "id": second_response.tool_calls[0].id,
                            "name": "lookup_time",
                            "response": {
                                "result": "3 PM",
                            },
                        }
                    }
                ],
            }
        ]
    }
    assert weather_response.text == "weather done"
    assert time_response.text == "time done"


@pytest.mark.asyncio
async def test_gemini_adapter_close_only_closes_owned_clients() -> None:
    class _ExternalClient:
        def __init__(self) -> None:
            self.close_calls = 0

        async def aclose(self) -> None:
            self.close_calls += 1

    external_client = _ExternalClient()
    external_adapter = unified_llm.GeminiAdapter(
        api_key="explicit-key",
        client=external_client,
    )
    await external_adapter.close()
    assert external_client.close_calls == 0

    owned_adapter = unified_llm.GeminiAdapter(
        api_key="explicit-key",
        transport=httpx.MockTransport(lambda request: httpx.Response(200)),
    )
    await owned_adapter.close()

    with pytest.raises(unified_llm.ConfigurationError, match="Gemini HTTP client is not available"):
        await owned_adapter.complete(
            unified_llm.Request(
                model="gemini-3.1-pro-preview",
                messages=[unified_llm.Message.user("hello")],
            )
        )
