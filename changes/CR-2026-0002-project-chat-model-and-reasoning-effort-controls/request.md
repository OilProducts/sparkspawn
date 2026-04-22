# Project Chat Model and Reasoning Effort Controls

## Summary
Add project-chat controls for model and reasoning effort first, independent of workflow LLM node runtime plumbing. Settings are per conversation thread, seeded from Global Settings, shown in the composer row, and sent to Codex app-server on each project-chat turn.

## Key Changes
- Add durable thread-level chat settings to conversation snapshots: `model?: string | null` and `reasoning_effort?: string | null`.
- Seed new/unspecified thread controls from `uiDefaults.llm_model` and `uiDefaults.reasoning_effort`; blank effort means “use model/Codex default.”
- Add a model metadata endpoint backed by Codex `model/list`, normalizing model id/display/default and supported/default reasoning efforts.
- Use model-aware reasoning effort options in the composer: options come from the selected model metadata, with a fallback to `low`, `medium`, `high`, `xhigh` if metadata is unavailable.
- Keep existing `/plan` and `/chat` command behavior unchanged.

## Implementation Changes
- Frontend: extend project chat state/view model/API types so the active thread exposes effective model and effort; render compact model and effort controls in the composer row next to Send.
- Frontend: load Codex model metadata for the active project, fall back to existing `llmSuggestions` if the endpoint fails, and keep the user’s current model value visible even if it is not in the returned list.
- Backend API: extend conversation turn/settings requests to accept optional `model` and `reasoning_effort`; persist both on `ConversationState` when changed or when a turn is sent.
- Chat runtime: extend `PreparedChatTurn`, `ProjectChatService`, `CodexAppServerChatSession.turn()`, and `CodexAppServerClient.run_turn()` to carry `reasoning_effort`.
- App-server request: include `reasoningEffort` on `turn/start` only when the resolved effort is non-empty; keep existing `model` and `collaborationMode` behavior intact.
- Validation: normalize effort to empty/null or one of `low`, `medium`, `high`, `xhigh`; leave model-specific support enforcement to Codex app-server because the model list can be unavailable or stale.

## Test Plan
- Backend unit/API tests:
  - conversation snapshots include persisted `model` and `reasoning_effort`;
  - turn requests persist and forward both values;
  - settings updates can change model/effort without sending a message;
  - blank effort omits `reasoningEffort` from `turn/start`;
  - Codex client model metadata parsing handles supported/default effort fields.
- Frontend tests:
  - composer initializes controls from Global Settings for a new thread;
  - switching threads shows each thread’s own model/effort;
  - changing controls sends/persists settings and subsequent chat turn payload includes them;
  - selected model changes update available effort options from metadata.
- Run full validation with `uv run pytest -q`.

## Assumptions
- Project chat is the first target; workflow node runtime handling for `reasoning_effort` remains a separate follow-up.
- Thread-scoped settings are persisted in conversation state, not only browser state.
- Model metadata comes from Codex app-server `model/list`; failures degrade to static model suggestions and generic effort choices.
