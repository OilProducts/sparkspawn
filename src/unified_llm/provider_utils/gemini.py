from __future__ import annotations

import copy
import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

from ..errors import InvalidRequestError, ProviderError, UnsupportedToolChoiceError
from ..streaming import StreamAccumulator
from ..tools import Tool, ToolCall, ToolChoice
from ..types import (
    ContentKind,
    ContentPart,
    FinishReason,
    ImageData,
    Message,
    Request,
    Response,
    Role,
    StreamEvent,
    StreamEventType,
    ThinkingData,
)
from .http import normalize_rate_limit, provider_options_for
from .media import prepare_gemini_image_block
from .normalization import (
    normalize_finish_reason,
    normalize_raw_payload,
    normalize_usage,
)
from .sse import aiter_sse_events

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com"
DEFAULT_GEMINI_API_VERSION = "v1beta"
_GEMINI_GENERATION_CONFIG_KEYS = {
    "candidateCount",
    "frequencyPenalty",
    "logprobs",
    "maxOutputTokens",
    "mediaResolution",
    "presencePenalty",
    "responseLogprobs",
    "responseMimeType",
    "responseSchema",
    "seed",
    "stopSequences",
    "temperature",
    "thinkingConfig",
    "topK",
    "topP",
}


def _coerce_text(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, (bytes, bytearray)):
        try:
            text = bytes(value).decode("utf-8")
        except UnicodeDecodeError:
            logger.debug("Unable to decode %s as UTF-8", field_name, exc_info=True)
            text = bytes(value).decode("utf-8", errors="replace")
        text = text.strip()
        return text or None
    logger.debug("Unexpected %s type: %s", field_name, type(value).__name__)
    return None


def _coerce_exact_text(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        try:
            return bytes(value).decode("utf-8")
        except UnicodeDecodeError:
            logger.debug("Unable to decode %s as UTF-8", field_name, exc_info=True)
            return bytes(value).decode("utf-8", errors="replace")
    logger.debug("Unexpected %s type: %s", field_name, type(value).__name__)
    return None


def _normalize_model_name(model: str) -> str:
    text = model.strip()
    if text.startswith("models/"):
        text = text.removeprefix("models/")
    return text


def _synthetic_tool_call_id(name: str | None) -> str:
    encoded_name = quote(name or "tool", safe="")
    return f"gemini_call_{encoded_name}_{uuid.uuid4().hex}"


def _part_thought_signature(part: Mapping[str, Any]) -> str | None:
    signature = _coerce_text(
        part.get("thoughtSignature"),
        field_name="response.part.thoughtSignature",
    )
    if signature is not None:
        return signature
    return _coerce_text(
        part.get("thought_signature"),
        field_name="response.part.thought_signature",
    )


def _part_thought_flag(part: Mapping[str, Any]) -> bool:
    thought = part.get("thought")
    if thought is None:
        return False
    if isinstance(thought, bool):
        return thought
    logger.debug(
        "Unexpected response.part.thought type: %s",
        type(thought).__name__,
    )
    return False


def _part_payload_thought_metadata(
    payload: dict[str, Any],
    part: ContentPart,
    *,
    thought: bool = False,
) -> dict[str, Any]:
    thinking = part.thinking
    if thought or part.kind in (ContentKind.THINKING, ContentKind.REDACTED_THINKING):
        payload["thought"] = True
    if thinking is not None and thinking.signature is not None:
        payload["thoughtSignature"] = thinking.signature
    return payload


def normalize_gemini_base_url(base_url: str | None) -> str:
    text = (base_url or "").strip() or DEFAULT_GEMINI_BASE_URL
    parts = urlsplit(text)
    path = parts.path.rstrip("/")

    for suffix in ("/generateContent", "/streamGenerateContent"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]

    if "/models/" in path:
        path = path.split("/models/", 1)[0]

    path = path.rstrip("/")
    if not path:
        path = f"/{DEFAULT_GEMINI_API_VERSION}"
    elif path.endswith("/v1beta"):
        pass
    elif path.endswith("/v1"):
        path = f"{path[:-len('/v1')]}/{DEFAULT_GEMINI_API_VERSION}"
    else:
        path = f"{path}/{DEFAULT_GEMINI_API_VERSION}"

    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def build_gemini_generate_content_url(base_url: str | None, model: str) -> str:
    normalized_base_url = normalize_gemini_base_url(base_url)
    parts = urlsplit(normalized_base_url)
    path = parts.path.rstrip("/")
    path = f"{path}/models/{quote(_normalize_model_name(model), safe='')}:generateContent"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def build_gemini_stream_generate_content_url(base_url: str | None, model: str) -> str:
    normalized_base_url = normalize_gemini_base_url(base_url)
    parts = urlsplit(normalized_base_url)
    path = parts.path.rstrip("/")
    path = f"{path}/models/{quote(_normalize_model_name(model), safe='')}:streamGenerateContent"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def _system_instruction_text(messages: Sequence[Message]) -> str | None:
    fragments: list[str] = []
    for message in messages:
        if message.role not in (Role.SYSTEM, Role.DEVELOPER):
            continue
        for part in message.content:
            if part.kind != ContentKind.TEXT:
                raise InvalidRequestError(
                    "Gemini system instructions must be text only",
                    provider="gemini",
                )
            if part.text is not None:
                fragments.append(part.text)
    if not fragments:
        return None
    return "\n\n".join(fragments)


def _ensure_json_serializable(value: Any, *, field_name: str) -> None:
    try:
        json.dumps(value, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        logger.exception("Unexpected failure serializing Gemini %s", field_name)
        raise InvalidRequestError(
            f"Gemini {field_name} must be JSON serializable",
            provider="gemini",
        ) from exc


def _deep_merge_mappings(
    base: Mapping[str, Any] | None,
    additions: Mapping[str, Any],
) -> dict[str, Any]:
    merged: dict[str, Any] = copy.deepcopy(dict(base or {}))
    for key, value in additions.items():
        existing = merged.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge_mappings(existing, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _gemini_native_provider_options(
    provider_options: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if provider_options is None:
        return {}, None

    native_provider_options = copy.deepcopy(dict(provider_options))
    native_provider_options.pop("structured_output", None)

    generation_config: dict[str, Any] = {}
    raw_generation_config = native_provider_options.pop("generationConfig", None)
    if raw_generation_config is not None:
        if not isinstance(raw_generation_config, Mapping):
            logger.debug(
                "Unexpected Gemini provider_options.gemini.generationConfig type: %s",
                type(raw_generation_config).__name__,
            )
            raise TypeError(
                "Gemini provider_options['gemini']['generationConfig'] must be a mapping or None"
            )
        generation_config = copy.deepcopy(dict(raw_generation_config))

    for key in _GEMINI_GENERATION_CONFIG_KEYS:
        if key in native_provider_options:
            generation_config[key] = native_provider_options.pop(key)

    return native_provider_options, generation_config or None


def _tool_definition(tool: Tool) -> dict[str, Any]:
    declaration: dict[str, Any] = {
        "name": tool.name,
    }
    if tool.description is not None:
        declaration["description"] = tool.description
    if tool.parameters is not None:
        declaration["parametersJsonSchema"] = copy.deepcopy(tool.parameters)
    return declaration


def _tool_config_payload(
    tool_choice: ToolChoice | None,
    *,
    tool_names: set[str],
) -> dict[str, Any] | None:
    selected_tool_choice = tool_choice
    if selected_tool_choice is None:
        if not tool_names:
            return None
        selected_tool_choice = ToolChoice.auto()

    if selected_tool_choice.is_auto:
        return {
            "functionCallingConfig": {
                "mode": "AUTO",
            }
        }

    if selected_tool_choice.is_none:
        return {
            "functionCallingConfig": {
                "mode": "NONE",
            }
        }

    if selected_tool_choice.is_required:
        if not tool_names:
            raise UnsupportedToolChoiceError(
                "Gemini tool_choice required requires at least one tool",
            )
        return {
            "functionCallingConfig": {
                "mode": "ANY",
            }
        }

    if selected_tool_choice.is_named:
        tool_name = selected_tool_choice.tool_name
        if tool_name is None or tool_name not in tool_names:
            raise UnsupportedToolChoiceError(
                f"Gemini tool_choice named {tool_name!r} requires a matching tool",
            )
        return {
            "functionCallingConfig": {
                "mode": "ANY",
                "allowedFunctionNames": [tool_name],
            }
        }

    raise UnsupportedToolChoiceError(
        f"Gemini tool_choice mode {selected_tool_choice.mode!r} is not supported",
    )


def _tool_call_arguments_payload(tool_call: Any) -> dict[str, Any]:
    arguments = getattr(tool_call, "arguments", None)
    if isinstance(arguments, Mapping):
        payload = copy.deepcopy(dict(arguments))
        _ensure_json_serializable(payload, field_name="tool_call.arguments")
        return payload

    if isinstance(arguments, str):
        text = arguments.strip()
        if not text:
            raise InvalidRequestError(
                "Gemini tool_call arguments must be a JSON object",
                provider="gemini",
            )
        try:
            parsed_arguments = json.loads(arguments)
        except json.JSONDecodeError as exc:
            logger.exception("Failed to parse Gemini tool_call arguments")
            raise InvalidRequestError(
                "Gemini tool_call arguments must be valid JSON object data",
                provider="gemini",
            ) from exc
        if not isinstance(parsed_arguments, Mapping):
            raise InvalidRequestError(
                "Gemini tool_call arguments must decode to a JSON object",
                provider="gemini",
            )
        payload = copy.deepcopy(dict(parsed_arguments))
        _ensure_json_serializable(payload, field_name="tool_call.arguments")
        return payload

    if arguments is None:
        raise InvalidRequestError(
            "Gemini tool_call arguments are required",
            provider="gemini",
        )

    raise InvalidRequestError(
        "Gemini tool_call arguments must be a mapping or JSON string",
        provider="gemini",
    )


def _tool_call_part_payload(
    part: ContentPart,
    *,
    tool_call_names: dict[str, str],
) -> dict[str, Any]:
    tool_call = part.tool_call
    if tool_call is None:
        raise InvalidRequestError(
            "Gemini tool_call content requires a tool_call payload",
            provider="gemini",
        )

    tool_call_id = _coerce_text(
        getattr(tool_call, "id", None),
        field_name="tool_call.id",
    )
    if tool_call_id is None:
        raise InvalidRequestError(
            "Gemini tool_call content requires a tool_call_id",
            provider="gemini",
        )

    name = _coerce_text(
        getattr(tool_call, "name", None),
        field_name="tool_call.name",
    )
    if name is None:
        raise InvalidRequestError(
            "Gemini tool_call content requires a function name",
            provider="gemini",
        )

    existing_name = tool_call_names.get(tool_call_id)
    if existing_name is None:
        tool_call_names[tool_call_id] = name
    elif existing_name != name:
        raise InvalidRequestError(
            (
                "Gemini tool_call id "
                f"{tool_call_id!r} is associated with both {existing_name!r} and {name!r}"
            ),
            provider="gemini",
        )

    arguments = _tool_call_arguments_payload(tool_call)
    return {
        "functionCall": {
            "name": name,
            "args": arguments,
        }
    }


def _tool_result_response_payload(tool_result: Any) -> dict[str, Any]:
    content = getattr(tool_result, "content", None)
    if isinstance(content, Mapping):
        response: dict[str, Any] = copy.deepcopy(dict(content))
    else:
        response = {"result": copy.deepcopy(content)}

    _ensure_json_serializable(response, field_name="tool_result.response")
    return response


def _tool_result_parts(
    part: ContentPart,
    *,
    message_name: str | None,
    message_tool_call_id: str | None,
    tool_name_lookup: Callable[[str], str | None] | None,
    tool_call_names: dict[str, str],
) -> list[dict[str, Any]]:
    tool_result = part.tool_result
    if tool_result is None:
        raise InvalidRequestError(
            "Gemini tool_result content requires a tool_result payload",
            provider="gemini",
        )

    tool_call_id = _coerce_text(
        getattr(tool_result, "tool_call_id", None),
        field_name="tool_result.tool_call_id",
    )
    if tool_call_id is None:
        raise InvalidRequestError(
            "Gemini tool_result content requires a tool_call_id",
            provider="gemini",
        )

    resolved_message_tool_call_id = _coerce_text(
        message_tool_call_id,
        field_name="message.tool_call_id",
    )
    if (
        resolved_message_tool_call_id is not None
        and resolved_message_tool_call_id != tool_call_id
    ):
        raise InvalidRequestError(
            "Gemini tool_result message tool_call_id must match the tool_result payload",
            provider="gemini",
        )

    name = _coerce_text(message_name, field_name="message.name")
    if name is None:
        name = tool_call_names.get(tool_call_id)

    if name is None and tool_name_lookup is not None:
        try:
            resolved_name = tool_name_lookup(tool_call_id)
        except Exception as exc:
            logger.exception(
                "Unexpected failure resolving Gemini tool_call_id %s",
                tool_call_id,
            )
            raise InvalidRequestError(
                (
                    "Gemini tool_result content requires a known function name "
                    f"for tool_call_id {tool_call_id!r}"
                ),
                provider="gemini",
            ) from exc
        name = _coerce_text(resolved_name, field_name="tool_result.function_name")

    if name is None:
        raise InvalidRequestError(
            (
                "Gemini tool_result content requires a known function name "
                f"for tool_call_id {tool_call_id!r}"
            ),
            provider="gemini",
        )

    parts: list[dict[str, Any]] = [
        {
            "functionResponse": {
                "id": tool_call_id,
                "name": name,
                "response": _tool_result_response_payload(tool_result),
            }
        }
    ]

    image_data = getattr(tool_result, "image_data", None)
    if image_data is not None:
        image_media_type = getattr(tool_result, "image_media_type", None)
        if not isinstance(image_data, (bytes, bytearray)):
            raise InvalidRequestError(
                "Gemini tool_result image_data must be bytes",
                provider="gemini",
            )
        try:
            image = ImageData(
                data=bytes(image_data),
                media_type=image_media_type,
            )
        except (TypeError, ValueError) as exc:
            raise InvalidRequestError(
                "Gemini tool_result image_data requires bytes and an optional media_type",
                provider="gemini",
            ) from exc
        parts.append(prepare_gemini_image_block(image))

    return parts


def _content_parts_from_mapping(item: Mapping[str, Any]) -> list[ContentPart]:
    function_call = item.get("functionCall")
    if function_call is None:
        function_call = item.get("function_call")
    if isinstance(function_call, Mapping):
        name = _coerce_text(
            function_call.get("name"),
            field_name="response.function_call.name",
        )
        arguments = function_call.get("args")
        if arguments is None:
            arguments = function_call.get("arguments")
        raw_arguments: str | None = None
        if isinstance(arguments, str):
            raw_arguments = arguments
            try:
                parsed_arguments = json.loads(arguments)
            except json.JSONDecodeError:
                parsed_arguments = arguments
            arguments = parsed_arguments
        elif isinstance(arguments, Mapping):
            parsed = copy.deepcopy(dict(arguments))
            raw_arguments = json.dumps(parsed, separators=(",", ":"), sort_keys=True)
            arguments = parsed
        elif arguments is None:
            arguments = {}
        else:
            try:
                raw_arguments = json.dumps(arguments, separators=(",", ":"), sort_keys=True)
            except Exception:
                raw_arguments = str(arguments)
            arguments = arguments

        call_id = _coerce_text(
            function_call.get("id") or function_call.get("functionCallId"),
            field_name="response.function_call.id",
        )
        if call_id is None:
            call_id = _synthetic_tool_call_id(name)

        signature = _part_thought_signature(item) or _part_thought_signature(function_call)
        thinking = (
            ThinkingData(text="", signature=signature)
            if signature is not None
            else None
        )
        return [
            ContentPart(
                kind=ContentKind.TOOL_CALL,
                tool_call=ToolCall(
                    id=call_id,
                    name=name or "tool",
                    arguments=arguments,
                    raw_arguments=raw_arguments,
                    type="function",
                ),
                thinking=thinking,
            )
        ]

    text = _coerce_exact_text(
        item.get("text") or item.get("content") or item.get("value"),
        field_name="response.part.text",
    )
    thought = _part_thought_flag(item)
    signature = _part_thought_signature(item)

    if text is None:
        if thought:
            thinking = ThinkingData(
                text="",
                signature=signature,
                redacted=False,
            )
            return [
                ContentPart(
                    kind=ContentKind.THINKING,
                    text="",
                    thinking=thinking,
                )
            ]
        return []

    if thought:
        thinking = ThinkingData(
            text=text,
            signature=signature,
            redacted=False,
        )
        return [
            ContentPart(
                kind=ContentKind.THINKING,
                text=text,
                thinking=thinking,
            )
        ]

    thinking = (
        ThinkingData(text=text, signature=signature, redacted=False)
        if signature is not None
        else None
    )
    return [
        ContentPart(
            kind=ContentKind.TEXT,
            text=text,
            thinking=thinking,
        )
    ]


def _message_payload(
    message: Message,
    *,
    tool_name_lookup: Callable[[str], str | None] | None,
    tool_call_names: dict[str, str],
) -> dict[str, Any]:
    if message.role not in (Role.USER, Role.ASSISTANT, Role.TOOL):
        raise InvalidRequestError(
            f"Gemini adapter does not support role {message.role}",
            provider="gemini",
        )

    role = "user" if message.role in (Role.USER, Role.TOOL) else "model"
    parts: list[dict[str, Any]] = []
    for part in message.content:
        if part.kind == ContentKind.TEXT:
            text = part.text
            if text is None and part.thinking is not None:
                text = part.thinking.text
            if text is not None:
                payload = {"text": text}
                parts.append(_part_payload_thought_metadata(payload, part))
            continue

        if part.kind in (ContentKind.THINKING, ContentKind.REDACTED_THINKING):
            thinking = part.thinking
            text = part.text
            if text is None and thinking is not None:
                text = thinking.text
            if text is None:
                continue
            payload = {"text": text}
            parts.append(_part_payload_thought_metadata(payload, part, thought=True))
            continue

        if part.kind == ContentKind.IMAGE:
            image = part.image
            if image is None:
                raise InvalidRequestError(
                    "Gemini image content requires an image payload",
                    provider="gemini",
                )
            parts.append(
                _part_payload_thought_metadata(
                    prepare_gemini_image_block(image),
                    part,
                )
            )
            continue

        if part.kind == ContentKind.TOOL_CALL:
            if message.role != Role.ASSISTANT:
                raise InvalidRequestError(
                    "Gemini tool_call content is only valid in assistant messages",
                    provider="gemini",
                )
            parts.append(
                _part_payload_thought_metadata(
                    _tool_call_part_payload(
                        part,
                        tool_call_names=tool_call_names,
                    ),
                    part,
                )
            )
            continue

        if part.kind == ContentKind.TOOL_RESULT:
            if message.role != Role.TOOL:
                raise InvalidRequestError(
                    "Gemini tool_result content is only valid in tool messages",
                    provider="gemini",
                )
            parts.extend(
                _tool_result_parts(
                    part,
                    message_name=message.name,
                    message_tool_call_id=message.tool_call_id,
                    tool_name_lookup=tool_name_lookup,
                    tool_call_names=tool_call_names,
                )
            )
            continue

        raise InvalidRequestError(
            f"Gemini adapter does not support content kind {part.kind}",
            provider="gemini",
        )

    return {"role": role, "parts": parts}


def build_gemini_generate_content_request(
    request: Request,
    *,
    tool_name_lookup: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"contents": []}

    system_instruction = _system_instruction_text(request.messages)
    if system_instruction is not None:
        body["systemInstruction"] = {
            "parts": [
                {
                    "text": system_instruction,
                }
            ]
        }

    tool_names = {tool.name for tool in request.tools or []}
    if request.tools:
        body["tools"] = [
            {
                "functionDeclarations": [
                    _tool_definition(tool) for tool in request.tools
                ]
            }
        ]

    tool_config = _tool_config_payload(request.tool_choice, tool_names=tool_names)
    if tool_config is not None:
        body["toolConfig"] = tool_config

    tool_call_names: dict[str, str] = {}
    for message in request.messages:
        if message.role in (Role.SYSTEM, Role.DEVELOPER):
            continue
        body["contents"].append(
            _message_payload(
                message,
                tool_name_lookup=tool_name_lookup,
                tool_call_names=tool_call_names,
            )
        )

    provider_options = provider_options_for(request, "gemini")
    native_provider_options, generation_config = _gemini_native_provider_options(
        provider_options
    )
    if native_provider_options:
        body = _deep_merge_mappings(body, native_provider_options)
    if generation_config:
        body["generationConfig"] = generation_config

    return body


def _parts_from_payload(value: Any) -> list[ContentPart]:
    if value is None:
        return []

    if isinstance(value, ContentPart):
        return [value]

    if isinstance(value, Mapping):
        if "parts" in value:
            return _parts_from_payload(value.get("parts"))
        return _content_parts_from_mapping(value)

    if isinstance(value, (str, bytes, bytearray)):
        text = _coerce_exact_text(value, field_name="response.content")
        if text is None:
            return []
        return [ContentPart(kind=ContentKind.TEXT, text=text)]

    if not isinstance(value, Sequence):
        text = _coerce_exact_text(value, field_name="response.content")
        if text is None:
            return []
        return [ContentPart(kind=ContentKind.TEXT, text=text)]

    parts: list[ContentPart] = []
    for item in value:
        if isinstance(item, ContentPart):
            parts.append(item)
            continue
        if not isinstance(item, Mapping):
            text = _coerce_exact_text(item, field_name="response.part")
            if text is not None:
                parts.append(ContentPart(kind=ContentKind.TEXT, text=text))
            continue
        parts.extend(_content_parts_from_mapping(item))

    return parts


def _response_from_mapping(
    source: Mapping[str, Any],
    *,
    provider: str,
    headers: Mapping[str, Any] | Any | None,
    raw: Any,
) -> Response:
    candidates = source.get("candidates")
    candidate: Mapping[str, Any] | None = None
    if (
        isinstance(candidates, Sequence)
        and not isinstance(candidates, (str, bytes, bytearray))
        and candidates
    ):
        first_candidate = candidates[0]
        if isinstance(first_candidate, Mapping):
            candidate = first_candidate

    content_source: Any = None
    if candidate is not None:
        content_source = candidate.get("content")
    elif "content" in source:
        content_source = source.get("content")
    elif "parts" in source:
        content_source = source.get("parts")

    content_parts: list[ContentPart] = []
    if isinstance(content_source, Mapping):
        content_parts = _parts_from_payload(content_source.get("parts") or content_source)
    else:
        content_parts = _parts_from_payload(content_source)

    finish_reason_value = None
    if candidate is not None:
        finish_reason_value = candidate.get("finishReason")
        if finish_reason_value is None:
            finish_reason_value = candidate.get("finish_reason")
    if finish_reason_value is None:
        finish_reason_value = source.get("finishReason")
    if finish_reason_value is None:
        finish_reason_value = source.get("finish_reason")

    finish_reason = normalize_finish_reason(finish_reason_value, provider=provider)
    if any(part.kind == ContentKind.TOOL_CALL for part in content_parts):
        finish_reason = FinishReason(
            reason=FinishReason.TOOL_CALLS,
            raw=finish_reason.raw,
        )

    response_id = _coerce_text(
        source.get("responseId") or source.get("response_id"),
        field_name="response.response_id",
    )
    model = _coerce_text(
        source.get("modelVersion") or source.get("model_version") or source.get("model"),
        field_name="response.model",
    )
    if response_id is None and candidate is not None:
        response_id = _coerce_text(candidate.get("responseId"), field_name="response.response_id")
    if model is None and candidate is not None:
        model = _coerce_text(candidate.get("modelVersion"), field_name="response.model")

    usage_payload = source.get("usageMetadata")
    if usage_payload is None:
        usage_payload = source.get("usage_metadata")
    if usage_payload is None and candidate is not None:
        usage_payload = candidate.get("usageMetadata")
    usage = normalize_usage(usage_payload, provider=provider, raw=usage_payload)

    return Response(
        id=response_id or "",
        model=model or "",
        provider=provider,
        message=Message(role=Role.ASSISTANT, content=content_parts),
        finish_reason=finish_reason,
        usage=usage,
        raw=raw,
        rate_limit=normalize_rate_limit(headers),
    )


def _merge_content_parts(
    current_parts: list[ContentPart],
    new_parts: list[ContentPart],
) -> list[ContentPart]:
    if not current_parts:
        return list(new_parts)
    if not new_parts:
        return current_parts

    if len(new_parts) >= len(current_parts) and new_parts[: len(current_parts)] == current_parts:
        return list(new_parts)

    if len(current_parts) >= len(new_parts) and current_parts[: len(new_parts)] == new_parts:
        return current_parts

    return current_parts + list(new_parts)


def _merge_gemini_response_chunks(
    current: Response,
    new: Response,
    *,
    provider: str,
    raw: Any,
) -> Response:
    finish_reason = current.finish_reason
    if new.finish_reason.raw is not None or new.finish_reason.reason != FinishReason.OTHER:
        finish_reason = new.finish_reason

    merged_content = _merge_content_parts(
        list(current.message.content),
        list(new.message.content),
    )
    if any(part.kind == ContentKind.TOOL_CALL for part in merged_content):
        finish_reason = FinishReason(
            reason=FinishReason.TOOL_CALLS,
            raw=finish_reason.raw,
        )

    usage = current.usage
    if new.usage.raw is not None:
        usage = new.usage

    rate_limit = new.rate_limit if new.rate_limit is not None else current.rate_limit

    return Response(
        id=new.id or current.id,
        model=new.model or current.model,
        provider=provider,
        message=Message(role=Role.ASSISTANT, content=merged_content),
        finish_reason=finish_reason,
        usage=usage,
        raw=raw,
        rate_limit=rate_limit,
    )


def _normalize_gemini_payload_sequence(
    source: Sequence[Any],
    *,
    provider: str,
    headers: Mapping[str, Any] | Any | None,
    raw: Any,
) -> Response:
    merged: Response | None = None
    for item in source:
        normalized_item = _normalize_gemini_payload(
            item,
            provider=provider,
            headers=headers,
            raw=item,
        )
        if merged is None:
            merged = normalized_item
            continue

        merged = _merge_gemini_response_chunks(
            merged,
            normalized_item,
            provider=provider,
            raw=raw,
        )

    if merged is None:
        return Response(
            provider=provider,
            raw=raw,
            rate_limit=normalize_rate_limit(headers),
        )

    return merged


def _normalize_gemini_payload(
    payload: Any,
    *,
    provider: str,
    headers: Mapping[str, Any] | Any | None,
    raw: Any,
) -> Response:
    source = normalize_raw_payload(payload)

    if isinstance(source, Sequence) and not isinstance(
        source,
        (str, bytes, bytearray),
    ):
        return _normalize_gemini_payload_sequence(
            source,
            provider=provider,
            headers=headers,
            raw=raw,
        )

    if isinstance(source, str):
        text = _coerce_exact_text(source, field_name="response")
        parts = [ContentPart(kind=ContentKind.TEXT, text=text)] if text is not None else []
        return Response(
            provider=provider,
            message=Message(role=Role.ASSISTANT, content=parts),
            finish_reason=FinishReason(reason=FinishReason.OTHER),
            usage=normalize_usage(None, provider=provider, raw=None),
            raw=raw,
            rate_limit=normalize_rate_limit(headers),
        )

    if isinstance(source, Mapping):
        return _response_from_mapping(
            source,
            provider=provider,
            headers=headers,
            raw=raw,
        )

    text = _coerce_exact_text(source, field_name="response")
    if text is None:
        return Response(
            provider=provider,
            raw=raw,
            rate_limit=normalize_rate_limit(headers),
        )

    return Response(
        provider=provider,
        message=Message(
            role=Role.ASSISTANT,
            content=[ContentPart(kind=ContentKind.TEXT, text=text)],
        ),
        finish_reason=FinishReason(reason=FinishReason.OTHER),
        usage=normalize_usage(None, provider=provider, raw=None),
        raw=raw,
        rate_limit=normalize_rate_limit(headers),
    )


def normalize_gemini_response(
    payload: Any,
    *,
    provider: str = "gemini",
    headers: Mapping[str, Any] | Any | None = None,
    raw: Any = None,
) -> Response:
    raw_payload = raw if raw is not None else payload
    try:
        return _normalize_gemini_payload(
            payload,
            provider=provider,
            headers=headers,
            raw=raw_payload,
        )
    except ProviderError:
        raise
    except Exception as exc:
        logger.exception("Unexpected failure normalizing Gemini response")
        raise ProviderError(
            "failed to normalize Gemini response",
            provider=provider,
            raw=raw_payload,
            cause=exc,
            retryable=False,
        ) from exc


def _stream_part_kind(part: ContentPart) -> str | None:
    if part.kind == ContentKind.TOOL_CALL:
        return "tool_call"
    if part.kind in (ContentKind.THINKING, ContentKind.REDACTED_THINKING):
        return "reasoning"
    if part.kind == ContentKind.TEXT:
        return "text"
    return None


def _stream_part_text(part: ContentPart) -> str | None:
    text = part.text
    if text is None and part.thinking is not None:
        text = part.thinking.text
    return _coerce_exact_text(text, field_name="response.part.text")


def _stream_tool_call_signature(tool_call: ToolCall) -> tuple[str, str | None, str]:
    raw_arguments = tool_call.raw_arguments
    if raw_arguments is None:
        arguments = tool_call.arguments
        if isinstance(arguments, Mapping):
            try:
                raw_arguments = json.dumps(
                    dict(arguments),
                    separators=(",", ":"),
                    sort_keys=True,
                )
            except Exception:
                raw_arguments = str(arguments)
        elif isinstance(arguments, (bytes, bytearray)):
            try:
                raw_arguments = bytes(arguments).decode("utf-8")
            except UnicodeDecodeError:
                raw_arguments = bytes(arguments).decode("utf-8", errors="replace")
        elif arguments is None:
            raw_arguments = None
        else:
            raw_arguments = str(arguments)
    return tool_call.name, raw_arguments, tool_call.type


def _stream_payload_items(raw_payload: Any) -> list[Any]:
    payload = normalize_raw_payload(raw_payload)
    if payload is None:
        return []
    if isinstance(payload, str):
        text = payload.strip()
        if not text or text == "[DONE]":
            return []
        raise ProviderError(
            "Gemini stream payload must be JSON data",
            provider="gemini",
            raw=raw_payload,
            retryable=False,
        )
    if isinstance(payload, Mapping):
        return [payload]
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        items = list(payload)
        if not all(isinstance(item, Mapping) for item in items):
            raise ProviderError(
                "Gemini stream payload sequence must contain JSON objects",
                provider="gemini",
                raw=raw_payload,
                retryable=False,
            )
        return items
    raise ProviderError(
        "Gemini stream payload must be a JSON object",
        provider="gemini",
        raw=raw_payload,
        retryable=False,
    )


async def _aiter_gemini_stream_payloads(response: httpx.Response) -> AsyncIterator[Any]:
    sse_lines: list[str] = []
    saw_sse_metadata = False

    async def _flush_sse_lines() -> AsyncIterator[Any]:
        nonlocal sse_lines, saw_sse_metadata
        if not sse_lines:
            saw_sse_metadata = False
            return

        async def _replay_lines() -> AsyncIterator[str]:
            for buffered_line in sse_lines:
                yield buffered_line

        async for event in aiter_sse_events(_replay_lines()):
            for item in _stream_payload_items(event.data):
                yield item

        sse_lines = []
        saw_sse_metadata = False

    async for line in response.aiter_lines():
        if line.endswith("\r"):
            line = line[:-1]

        if line == "":
            async for item in _flush_sse_lines():
                yield item
            continue

        if line.startswith("data:"):
            saw_sse_metadata = True
            sse_lines.append(line)
            continue

        if line.startswith(("event:", "id:", "retry:", ":")):
            saw_sse_metadata = True
            sse_lines.append(line)
            continue

        if saw_sse_metadata and sse_lines:
            async for item in _flush_sse_lines():
                yield item

        for item in _stream_payload_items(line):
            yield item

    async for item in _flush_sse_lines():
        yield item


@dataclass(slots=True)
class _GeminiStreamState:
    provider: str
    headers: Mapping[str, Any] | Any | None
    accumulator: StreamAccumulator = field(default_factory=StreamAccumulator)
    raw_payloads: list[Any] = field(default_factory=list)
    started: bool = False
    active_text: str | None = None
    active_reasoning: str | None = None
    emitted_tool_calls: list[tuple[str, str | None, str]] = field(default_factory=list)
    last_response: Response | None = None
    last_raw_payload: Any = None

    def translate(self, payload: Any, *, raw: Any) -> list[StreamEvent]:
        response = normalize_gemini_response(
            payload,
            provider=self.provider,
            headers=self.headers,
            raw=raw,
        )
        response = replace(response, raw=None)
        self.last_response = response
        self.last_raw_payload = raw

        events: list[StreamEvent] = []
        if not self.started:
            self.started = True
            start_event = StreamEvent(
                type=StreamEventType.STREAM_START,
                response=replace(response, raw=None),
                raw=raw,
            )
            self.accumulator.add(start_event)
            events.append(start_event)

        events.extend(self._translate_content(response.message.content, raw=raw))
        return events

    def finalize(self) -> tuple[Response, Any, list[StreamEvent]]:
        close_raw = self.last_raw_payload
        close_events: list[StreamEvent] = []
        if self.active_reasoning is not None:
            event = StreamEvent(
                type=StreamEventType.REASONING_END,
                reasoning_delta=self.active_reasoning,
                raw=close_raw,
            )
            self.accumulator.add(event)
            close_events.append(event)
            self.active_reasoning = None

        if self.active_text is not None:
            event = StreamEvent(
                type=StreamEventType.TEXT_END,
                delta=self.active_text,
                raw=close_raw,
            )
            self.accumulator.add(event)
            close_events.append(event)
            self.active_text = None

        response = self.accumulator.response
        raw = self._resolved_raw()
        if self.last_response is None:
            return (
                replace(
                    response,
                    provider=self.provider,
                    raw=raw,
                    rate_limit=normalize_rate_limit(self.headers),
                ),
                raw,
                close_events,
            )

        finish_reason = self.last_response.finish_reason
        if response.tool_calls:
            finish_reason = FinishReason(
                reason=FinishReason.TOOL_CALLS,
                raw=finish_reason.raw,
            )

        return (
            replace(
                response,
                id=self.last_response.id or response.id,
                model=self.last_response.model or response.model,
                provider=self.provider,
                finish_reason=finish_reason,
                usage=self.last_response.usage,
                raw=raw,
                rate_limit=self.last_response.rate_limit or response.rate_limit,
            ),
            raw,
            close_events,
        )

    def _resolved_raw(self) -> Any:
        if not self.raw_payloads:
            return None
        if len(self.raw_payloads) == 1:
            return self.raw_payloads[0]
        return list(self.raw_payloads)

    def _translate_content(self, parts: Sequence[ContentPart], *, raw: Any) -> list[StreamEvent]:
        current_tool_call_signatures = [
            _stream_tool_call_signature(part.tool_call)
            for part in parts
            if _stream_part_kind(part) == "tool_call" and part.tool_call is not None
        ]
        prefix_length = 0
        max_prefix_length = min(
            len(self.emitted_tool_calls),
            len(current_tool_call_signatures),
        )
        while (
            prefix_length < max_prefix_length
            and (
                self.emitted_tool_calls[prefix_length]
                == current_tool_call_signatures[prefix_length]
            )
        ):
            prefix_length += 1

        runs: list[tuple[str, list[ContentPart]]] = []
        current_kind: str | None = None
        current_parts: list[ContentPart] = []

        for part in parts:
            kind = _stream_part_kind(part)
            if kind is None:
                if current_parts:
                    runs.append((current_kind or "", current_parts))
                    current_parts = []
                    current_kind = None
                continue

            if current_kind is None or kind != current_kind:
                if current_parts:
                    runs.append((current_kind or "", current_parts))
                current_kind = kind
                current_parts = [part]
            else:
                current_parts.append(part)

        if current_parts:
            runs.append((current_kind or "", current_parts))

        events: list[StreamEvent] = []
        tool_call_index = 0
        for index, (kind, run_parts) in enumerate(runs):
            next_kind = runs[index + 1][0] if index + 1 < len(runs) else None

            if kind == "text":
                segment = "".join(
                    text
                    for text in (_stream_part_text(part) for part in run_parts)
                    if text is not None
                )
                events.extend(self._emit_text_segment(segment, raw=raw))
                if next_kind is not None and next_kind != "text":
                    events.extend(self._close_text(raw))
                continue

            if kind == "reasoning":
                segment = "".join(
                    text
                    for text in (_stream_part_text(part) for part in run_parts)
                    if text is not None
                )
                events.extend(self._emit_reasoning_segment(segment, raw=raw))
                if next_kind is not None and next_kind != "reasoning":
                    events.extend(self._close_reasoning(raw))
                continue

            if kind == "tool_call":
                for part in run_parts:
                    events.extend(self._close_text(raw))
                    events.extend(self._close_reasoning(raw))
                    tool_call = part.tool_call
                    if tool_call is None:
                        continue
                    signature = current_tool_call_signatures[tool_call_index]
                    if tool_call_index < prefix_length:
                        tool_call_index += 1
                        continue
                    self.emitted_tool_calls.append(signature)
                    events.extend(self._emit_tool_call(tool_call, raw=raw))
                    tool_call_index += 1
                continue

        return events

    def _emit_text_segment(self, segment: str, *, raw: Any) -> list[StreamEvent]:
        if not segment:
            return []

        events: list[StreamEvent] = []
        if self.active_reasoning is not None:
            events.extend(self._close_reasoning(raw))

        if self.active_text is None:
            self.active_text = segment
            events.append(
                StreamEvent(
                    type=StreamEventType.TEXT_START,
                    raw=raw,
                )
            )
            events.append(
                StreamEvent(
                    type=StreamEventType.TEXT_DELTA,
                    delta=segment,
                    raw=raw,
                )
            )
            return events

        current = self.active_text
        if segment == current or current.startswith(segment):
            return events

        if segment.startswith(current):
            fragment = segment[len(current) :]
            if fragment:
                events.append(
                    StreamEvent(
                        type=StreamEventType.TEXT_DELTA,
                        delta=fragment,
                        raw=raw,
                    )
                )
            self.active_text = segment
            return events

        events.append(
            StreamEvent(
                type=StreamEventType.TEXT_DELTA,
                delta=segment,
                raw=raw,
            )
        )
        self.active_text = current + segment
        return events

    def _emit_reasoning_segment(self, segment: str, *, raw: Any) -> list[StreamEvent]:
        if not segment:
            return []

        events: list[StreamEvent] = []
        if self.active_text is not None:
            events.extend(self._close_text(raw))

        if self.active_reasoning is None:
            self.active_reasoning = segment
            events.append(
                StreamEvent(
                    type=StreamEventType.REASONING_START,
                    raw=raw,
                )
            )
            events.append(
                StreamEvent(
                    type=StreamEventType.REASONING_DELTA,
                    reasoning_delta=segment,
                    raw=raw,
                )
            )
            return events

        current = self.active_reasoning
        if segment == current or current.startswith(segment):
            return events

        if segment.startswith(current):
            fragment = segment[len(current) :]
            if fragment:
                events.append(
                    StreamEvent(
                        type=StreamEventType.REASONING_DELTA,
                        reasoning_delta=fragment,
                        raw=raw,
                    )
                )
            self.active_reasoning = segment
            return events

        events.append(
            StreamEvent(
                type=StreamEventType.REASONING_DELTA,
                reasoning_delta=segment,
                raw=raw,
            )
        )
        self.active_reasoning = current + segment
        return events

    def _emit_tool_call(self, tool_call: ToolCall, *, raw: Any) -> list[StreamEvent]:
        started_call = ToolCall(
            id=tool_call.id,
            name=tool_call.name,
            arguments=tool_call.arguments,
            raw_arguments=tool_call.raw_arguments,
            type=tool_call.type,
        )
        events = [
            StreamEvent(
                type=StreamEventType.TOOL_CALL_START,
                tool_call=started_call,
                raw=raw,
            ),
            StreamEvent(
                type=StreamEventType.TOOL_CALL_END,
                tool_call=started_call,
                raw=raw,
            ),
        ]
        for event in events:
            self.accumulator.add(event)
        return events

    def _close_text(self, raw: Any) -> list[StreamEvent]:
        if self.active_text is None:
            return []

        event = StreamEvent(
            type=StreamEventType.TEXT_END,
            delta=self.active_text,
            raw=raw,
        )
        self.active_text = None
        self.accumulator.add(event)
        return [event]

    def _close_reasoning(self, raw: Any) -> list[StreamEvent]:
        if self.active_reasoning is None:
            return []

        event = StreamEvent(
            type=StreamEventType.REASONING_END,
            reasoning_delta=self.active_reasoning,
            raw=raw,
        )
        self.active_reasoning = None
        self.accumulator.add(event)
        return [event]


async def normalize_gemini_stream_events(
    response: httpx.Response,
    *,
    provider: str = "gemini",
) -> AsyncIterator[StreamEvent]:
    state = _GeminiStreamState(provider=provider, headers=response.headers)

    try:
        async for payload in _aiter_gemini_stream_payloads(response):
            state.raw_payloads.append(payload)
            try:
                translated_events = state.translate(payload, raw=payload)
            except Exception as exc:
                logger.exception("Unexpected failure normalizing Gemini stream payload")
                yield StreamEvent(
                    type=StreamEventType.ERROR,
                    error=ProviderError(
                        "failed to normalize Gemini stream payload",
                        provider=provider,
                        raw=payload,
                        cause=exc,
                        retryable=False,
                    ),
                    raw=payload,
                )
                return

            for event in translated_events:
                yield event
                if event.type in (StreamEventType.FINISH, StreamEventType.ERROR):
                    return
    except Exception as exc:
        logger.exception("Unexpected failure reading Gemini stream payloads")
        raw_payload = getattr(exc, "raw", None)
        if raw_payload is None:
            raw_payload = getattr(response, "text", None)
        yield StreamEvent(
            type=StreamEventType.ERROR,
            error=ProviderError(
                "failed to read Gemini stream payloads",
                provider=provider,
                raw=raw_payload,
                cause=exc,
                retryable=False,
            ),
            raw=raw_payload,
        )
        return

    final_response, final_raw, final_events = state.finalize()
    if not state.started:
        start_event = StreamEvent(
            type=StreamEventType.STREAM_START,
            response=replace(final_response, raw=None),
            raw=None,
        )
        yield start_event
        yield StreamEvent(
            type=StreamEventType.FINISH,
            finish_reason=final_response.finish_reason,
            usage=final_response.usage,
            response=final_response,
            raw=final_raw,
        )
        return

    for event in final_events:
        yield event
    finish_event = StreamEvent(
        type=StreamEventType.FINISH,
        finish_reason=final_response.finish_reason,
        usage=final_response.usage,
        response=final_response,
        raw=final_raw,
    )
    state.accumulator.add(finish_event)
    yield finish_event


__all__ = [
    "DEFAULT_GEMINI_API_VERSION",
    "DEFAULT_GEMINI_BASE_URL",
    "build_gemini_generate_content_request",
    "build_gemini_generate_content_url",
    "build_gemini_stream_generate_content_url",
    "normalize_gemini_base_url",
    "normalize_gemini_response",
    "normalize_gemini_stream_events",
]
