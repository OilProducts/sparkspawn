//! Shared segment identity derivation for streamed turn events.
//!
//! Chat and run transcripts must derive the same segment id for every event
//! that targets the same logical segment, so streamed deltas coalesce instead
//! of duplicating rows. `turn_scope_key` is the fallback identity scope when
//! the event carries no provider ids: the assistant turn id for project chat,
//! the node scope for run transcripts.

use serde_json::{json, Map, Value};
use spark_common::events::TurnStreamEvent;

pub fn reasoning_segment_id(turn_scope_key: &str, event: &TurnStreamEvent) -> String {
    let app_turn_id = source_or(event.source.app_turn_id.as_deref(), turn_scope_key);
    let item_id = source_or(event.source.item_id.as_deref(), "reasoning");
    let summary_index = event.source.summary_index.unwrap_or(0);
    format!("segment-reasoning-{app_turn_id}-{item_id}-{summary_index}")
}

pub fn assistant_segment_id(turn_scope_key: &str, event: &TurnStreamEvent) -> String {
    match (
        non_empty(event.source.app_turn_id.as_deref()),
        non_empty(event.source.item_id.as_deref()),
    ) {
        (Some(app_turn_id), Some(item_id)) => format!("segment-assistant-{app_turn_id}-{item_id}"),
        _ => format!("segment-assistant-{turn_scope_key}"),
    }
}

pub fn plan_segment_id(turn_scope_key: &str, event: &TurnStreamEvent) -> String {
    match (
        non_empty(event.source.app_turn_id.as_deref()),
        non_empty(event.source.item_id.as_deref()),
    ) {
        (Some(app_turn_id), Some(item_id)) => format!("segment-plan-{app_turn_id}-{item_id}"),
        _ => format!("segment-plan-{turn_scope_key}"),
    }
}

pub fn context_compaction_segment_id(turn_scope_key: &str, event: &TurnStreamEvent) -> String {
    let app_turn_id = source_or(event.source.app_turn_id.as_deref(), turn_scope_key);
    format!("segment-context-compaction-{app_turn_id}")
}

pub fn tool_segment_id(turn_scope_key: &str, event: &TurnStreamEvent, tool_call: &Value) -> String {
    let app_turn_id = source_or(event.source.app_turn_id.as_deref(), turn_scope_key);
    let call_id = tool_call_id(tool_call)
        .or_else(|| non_empty(event.source.item_id.as_deref()).map(str::to_string))
        .unwrap_or_else(|| "tool".to_string());
    format!("segment-tool-{app_turn_id}-{call_id}")
}

pub fn model_tool_segment_id(
    turn_scope_key: &str,
    event: &TurnStreamEvent,
    tool_call: &Value,
) -> String {
    let app_turn_id = source_or(event.source.app_turn_id.as_deref(), turn_scope_key);
    let call_id = tool_call_id(tool_call)
        .or_else(|| non_empty(event.source.item_id.as_deref()).map(str::to_string))
        .unwrap_or_else(|| "model-tool".to_string());
    format!("segment-model-tool-{app_turn_id}-{call_id}")
}

pub fn request_user_input_segment_id(
    turn_scope_key: &str,
    event: &TurnStreamEvent,
    request: &Map<String, Value>,
) -> String {
    let app_turn_id = source_or(event.source.app_turn_id.as_deref(), turn_scope_key);
    let request_id = request
        .get("request_id")
        .and_then(Value::as_str)
        .and_then(|value| non_empty(Some(value)))
        .or_else(|| non_empty(event.source.item_id.as_deref()))
        .unwrap_or("request");
    format!("segment-request-user-input-{app_turn_id}-{request_id}")
}

/// Mirrors `spark_common::segments::agent_event_segment_id`: identity comes
/// only from durable provider facts (app turn + item id, app turn + kind for
/// singleton lifecycle events, provider-event sequence for repeatable itemless
/// events) — never from the mutable order counter.
pub fn agent_event_segment_id(
    turn_scope_key: &str,
    event: &TurnStreamEvent,
    provider_sequence: Option<u64>,
) -> String {
    let kind = non_empty(event.source.raw_kind.as_deref())
        .map(str::to_string)
        .unwrap_or_else(|| event.kind.as_str().to_string());
    let scope = non_empty(event.source.app_turn_id.as_deref())
        .map(str::to_string)
        .unwrap_or_else(|| turn_scope_key.to_string());
    if let Some(item_id) = non_empty(event.source.item_id.as_deref()) {
        return format!("segment-agent-event-{scope}-{kind}-{item_id}");
    }
    if spark_common::segments::is_singleton_lifecycle_event_kind(&kind) {
        return format!("segment-agent-event-{scope}-{kind}");
    }
    match provider_sequence {
        Some(sequence) => format!("segment-agent-event-{scope}-{kind}-seq{sequence}"),
        None => format!("segment-agent-event-{scope}-{kind}"),
    }
}

pub fn tool_call_id(tool_call: &Value) -> Option<String> {
    tool_call
        .get("id")
        .and_then(Value::as_str)
        .and_then(|value| non_empty(Some(value)))
        .map(str::to_string)
}

/// Provider provenance persisted on a segment, in the historical field order
/// and presence rules.
pub fn segment_source(event: &TurnStreamEvent, call_id: Option<&str>) -> Value {
    let mut source = Map::new();
    if let Some(value) = non_empty(event.source.backend.as_deref()) {
        source.insert("backend".to_string(), json!(value));
    }
    if let Some(value) = non_empty(event.source.session_id.as_deref()) {
        source.insert("session_id".to_string(), json!(value));
    }
    if let Some(value) = non_empty(event.source.app_thread_id.as_deref()) {
        source.insert("app_thread_id".to_string(), json!(value));
    }
    if let Some(value) = non_empty(event.source.app_turn_id.as_deref()) {
        source.insert("app_turn_id".to_string(), json!(value));
    }
    if let Some(value) = non_empty(event.source.item_id.as_deref()) {
        source.insert("item_id".to_string(), json!(value));
    }
    if let Some(value) = event.source.summary_index {
        source.insert("summary_index".to_string(), json!(value));
    }
    if let Some(value) = non_empty(event.source.response_id.as_deref()) {
        source.insert("response_id".to_string(), json!(value));
    }
    if let Some(value) = non_empty(event.source.raw_kind.as_deref()) {
        source.insert("raw_kind".to_string(), json!(value));
    }
    if let Some(value) = non_empty(call_id) {
        source.insert("call_id".to_string(), json!(value));
    }
    Value::Object(source)
}

fn source_or<'a>(value: Option<&'a str>, fallback: &'a str) -> &'a str {
    non_empty(value).unwrap_or(fallback)
}

fn non_empty(value: Option<&str>) -> Option<&str> {
    value.map(str::trim).filter(|value| !value.is_empty())
}
