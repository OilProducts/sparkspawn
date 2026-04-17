# Durable `request_user_input` Answer Delivery for Project Chat

## Summary

Make `request_user_input` answers durable end to end so a submitted card answer reliably reaches the owning agent, even if the original in-memory waiting session is gone.

- Submitted answers are persisted as durable conversation state, not treated as valid only while an in-memory pending request exists
- The owning conversation automatically resumes delivery when its session becomes available again
- Answered cards remain scoped to their conversation and keep the existing compressed-summary history behavior
- The current “live session must still be waiting” requirement is removed from the submission contract

## Key Changes

- Add durable pending-answer state to the persisted `request_user_input` record:
  - Extend the conversation-side request record so Spark can distinguish `answered in UI` from `delivered back to the waiting agent`
  - Persist enough metadata to track request id, submitted answers, submitted timestamp, and delivery status for the owning conversation

- Change backend submission semantics in Project Chat:
  - `submit_request_user_input_answer` should always validate and persist the answer against the owning conversation/request artifact
  - Do not reject solely because `ProjectChatService` lacks a live in-memory session or pending wait for that request
  - If the owning session is currently live and waiting, deliver immediately
  - If not, leave the answer queued durably for later delivery

- Add automatic resume/delivery in the session lifecycle:
  - When the owning conversation session is created, resumed, or reattached, Spark should check persisted conversation state for undelivered answered `request_user_input` records
  - If the app-server session is currently waiting on that request, submit the queued answers automatically and mark them delivered
  - No explicit user “resume” action is required; the owning conversation continues automatically once the session can accept the answer

- Tighten conversation ownership and artifact behavior:
  - Delivery is always keyed to the conversation that owns the `request_user_input` artifact
  - Answering from another open conversation view must still target the owning conversation/request record, not ambient UI state
  - The visible request card should continue to compress to answered summary after submission, but the underlying record must keep delivery status until the agent has consumed it

- Update failure handling and UI expectations:
  - “Conversation is not waiting for that user input request” should no longer be the normal answer-submission failure for durable cards
  - Real failures should be limited to invalid request id, wrong project/conversation binding, invalid answer shape, or duplicate conflicting answer attempts
  - If delivery is queued rather than immediate, the snapshot should still reflect successful submission

## Interfaces and Behavior Changes

- Extend the persisted `request_user_input` payload with durable delivery state:
  - keep existing answer fields
  - add explicit delivery status such as `pending_delivery` vs `delivered`
  - keep `submitted_at`; add `delivered_at` if needed for audit clarity

- Update Project Chat service/session behavior:
  - submission API becomes “persist first, deliver immediately if possible”
  - session bootstrap/resume path gains “replay undelivered answers for this conversation” behavior
  - in-memory pending maps remain an optimization for immediate delivery, not the source of truth

- Preserve current frontend interaction contract:
  - same submit endpoint shape
  - same inline-only unanswered card
  - same compressed answered summary after submission
  - no new user action required to continue the turn

## Test Plan

- Backend/service test: answering a `request_user_input` request persists the answer even when no live session is present
- Backend/service test: a queued durable answer is automatically delivered when the owning conversation session resumes and waits on that request
- Backend/service test: immediate live-session answers still resume the blocked turn without regression
- Backend/service test: answers remain scoped to the owning conversation and are not consumed by another conversation
- Backend/service test: duplicate identical submissions are idempotent; conflicting second answers are rejected cleanly
- Backend/service test: answered request segments remain compact answered summaries in the snapshot while retaining durable delivery metadata internally
- API test: `POST /api/conversations/{conversation_id}/request-user-input/{request_id}/answer` succeeds for durable queued delivery instead of returning the current waiting-session error
- Regression test: the request-user-input card path works across session churn/reload, not just with a stubbed always-live session
- Full validation gate: `uv run pytest -q`

## Assumptions

- `Durable delivery` is the intended product behavior
- Automatic continuation in the owning conversation is desired once the session can consume the answer
- The current inline-only unanswered UX and compressed-summary answered UX remain unchanged
- Delivery guarantees are conversation-scoped, not global across threads or projects
