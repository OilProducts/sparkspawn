# Conversation Event Contract

This document defines the strict event-driven contract for Spark Spawn project chat.

It exists to prevent ambiguity between:
- raw Codex app-server JSON-RPC notifications
- Spark Spawn normalized conversation events
- persisted conversation history
- live UI rendering

Source of truth for broader conversation lifecycle and storage:
- `conversation-paradigm.md`
- `storage-boundaries.md`
- `conversation-state-model.md`

## Purpose

Spark Spawn chat must follow a disciplined event model:
- raw app-server events are backend input
- normalized Spark Spawn events are the only UI event surface
- persisted history is durable and compact
- live rendering must not infer behavior from incidental snapshot fields

This contract is based on the official Codex model:
- normalize protocol events first
- maintain stable turn identity
- stream live output into dedicated UI surfaces
- commit durable history only when semantically complete

## Event Layers

### Layer 1: Raw Codex App-Server Notifications

These are backend-internal protocol inputs.

Examples:
- `item/agentMessage/delta`
- `codex/event/agent_message`
- `item/reasoning/summaryPartAdded`
- `item/reasoning/summaryTextDelta`
- `item/commandExecution/outputDelta`
- `item/started`
- `item/completed`
- `turn/completed`
- `codex/event/task_complete`
- `error`

Raw notifications MUST NOT be rendered directly by the frontend.

The backend MUST normalize them into Spark Spawn conversation events before they are exposed over the conversation SSE/API surface.

### Layer 2: Spark Spawn Normalized Conversation Events

These are the only live events the frontend may consume for chat rendering.

Allowed normalized event kinds:
- `turn_upsert`
- `assistant_delta`
- `reasoning_summary`
- `tool_call_started`
- `tool_call_updated`
- `tool_call_completed`
- `tool_call_failed`
- `assistant_completed`
- `assistant_failed`
- `retry_started`

### Layer 3: Durable Conversation State

Durable conversation state consists of:
- conversations
- turns
- materialized render segments
- workspace artifacts and provenance

The canonical durable state model is defined in:
- `conversation-state-model.md`

It MUST live under:
- `SPARKSPAWN_HOME/workspace/projects/<project-id>/conversations/`

Live-only transient state may exist in memory during a turn, but it MUST NOT become the durable source of truth unless explicitly materialized as a durable event or finalized turn state.

## Normalization Rules

### Assistant Text

Raw inputs:
- `item/agentMessage/delta`
- fallback `codex/event/agent_message_delta`
- completion-time whole-message signals such as `codex/event/agent_message` or `codex/event/task_complete`

Normalized outputs:
- `assistant_delta`
- `assistant_completed`
- `assistant_failed`

Rules:
- `assistant_delta` is the only live event allowed to update visible assistant response text during an active turn.
- `turn_upsert.content` MUST NOT be used to render live assistant prose while the assistant turn is `pending` or `streaming`.
- whole-message completion payloads may finalize the assistant turn and may backfill missing final text, but they MUST NOT create a duplicate visible assistant response.

### Reasoning Summaries

Raw inputs:
- `item/reasoning/summaryPartAdded`
- `item/reasoning/summaryTextDelta`

Normalized outputs:
- `reasoning_summary`

Rules:
- `summaryPartAdded` is the preferred source for coherent safe reasoning summaries.
- `summaryTextDelta` MUST NOT be rendered directly to users.
- `reasoning_summary` events are for the dedicated thinking surface only.
- `reasoning_summary` MUST NOT append or overwrite assistant response text.
- live reasoning summaries are not ordinary assistant messages.
- durable reasoning reconstruction is defined by `conversation-state-model.md`, which requires reasoning content to collapse into stable render segments rather than remain raw delta history.

### Tool Calls

Raw inputs may include:
- command execution lifecycle
- file change lifecycle
- dynamic tool call lifecycle

Normalized outputs:
- `tool_call_started`
- `tool_call_updated`
- `tool_call_completed`
- `tool_call_failed`

Rules:
- tool activity MUST remain attached to the active assistant turn
- tool output deltas MUST mutate the existing tool-call item for that call id
- a tool call MUST have one stable `tool_call_id`
- repeated output for the same tool call updates the existing tool item; it does not create a new call

### Turn Lifecycle

Raw inputs:
- assistant-turn start and completion signals
- terminal error conditions

Normalized outputs:
- `turn_upsert`
- `assistant_completed`
- `assistant_failed`
- `retry_started`

Rules:
- `turn_upsert` establishes turn identity and turn status
- `turn_upsert` is metadata, not a primary live-content stream
- `assistant_completed` finalizes the assistant turn
- `assistant_failed` finalizes a visible failure state
- `retry_started` is required for visible retry behavior; retries MUST NOT be silent

## Persistence Rules

### Persisted

The following are durable:
- conversation records
- turn records
- materialized render segments
- workspace artifacts and provenance
- coarse workflow/event log entries

### Not Persisted As Raw Live Stream

The following MUST NOT be treated as durable append-only transcript facts by default:
- raw protocol notifications
- token-like reasoning deltas
- partial assistant content snapshots

Assistant streaming deltas may be compacted into the final assistant turn content rather than retained forever as raw deltas.

Reasoning summaries MUST NOT be persisted as raw append-only delta history in `state.json`.

Instead, reasoning content MUST be compacted into durable render segments as defined by `conversation-state-model.md`, and those segments MUST remain distinct from assistant message content.

## Frontend Rendering Contract

### `turn_upsert`

The frontend may use `turn_upsert` to:
- create a missing turn shell
- update turn metadata
- update turn status
- finalize completed or failed turn content

The frontend MUST NOT use `turn_upsert.content` as the primary source of live assistant text while a turn is active.

### `assistant_delta`

The frontend MUST use `assistant_delta` to drive the live assistant response block.

Rules:
- one active assistant response block per assistant turn
- additional `assistant_delta` content extends that block
- tool activity may appear before, between, or after assistant deltas
- completion finalizes the same assistant response block rather than creating a second one

### `reasoning_summary`

The frontend MUST use `reasoning_summary` only for the thinking block.

Rules:
- one active thinking block per assistant turn
- additional `reasoning_summary` content extends that block
- the thinking block is separate from the assistant response block
- assistant deltas and thinking summaries must never overwrite each other

### `tool_call_*`

The frontend MUST render tool-call items as their own timeline entries or live cells.

Rules:
- tool-call updates mutate the matching tool-call item by `tool_call_id`
- tool output extends the existing item
- completion/failure updates the same item

### Completion

When `assistant_completed` arrives:
- the active assistant response block becomes final
- the thinking block remains separate
- no duplicate assistant message may be inserted

When `assistant_failed` arrives:
- the assistant response block enters a visible failed state
- any active tool items remain visible as part of the turn record

## Ordering Rules

Ordering MUST be determined by normalized event order within a stable assistant turn.

The system MUST NOT reorder transcript items by opportunistically replacing the entire conversation snapshot.

Within a single assistant turn:
- event order defines render order
- reasoning and assistant text are separate streams
- tool-call items occupy their own position in that order

Snapshot reloads may restore durable state, but they MUST reconcile with stable turn identity and stable event identity rather than re-deriving a different order from scratch.

## Snapshot Rules

Snapshots are allowed for:
- initial thread load
- reconnect recovery
- durable persistence checkpoints

Snapshots are not the live event stream.

Rules:
- live rendering MUST be event-driven
- snapshots MUST NOT invent live assistant text that was never emitted as `assistant_delta`
- snapshots MAY provide finalized completed turn content
- snapshots MAY omit compacted transient deltas as long as the resulting durable turn remains semantically correct

## Strict Prohibitions

Spark Spawn chat MUST NOT:
- render raw app-server reasoning text deltas directly
- render live assistant text from `turn_upsert.content` while the turn is active
- allow thinking summaries to overwrite assistant text
- allow assistant text to overwrite the thinking block
- create duplicate visible assistant replies for one completed turn
- silently retry a turn without emitting `retry_started`
- rebuild visible ordering from whole-snapshot replacement alone

## Implementation Target

The intended steady-state model is:
- backend consumes raw Codex app-server notifications
- backend emits only normalized Spark Spawn conversation events
- frontend renders live chat from normalized events
- durable snapshots remain compact and semantically complete

This document is the source of truth when event normalization, persistence, or live rendering behavior is ambiguous.
