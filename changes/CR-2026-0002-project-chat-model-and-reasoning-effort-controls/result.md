---
id: CR-2026-0002-project-chat-model-and-reasoning-effort-controls
title: Project Chat Model and Reasoning Effort Controls
status: completed
type: feature
changelog: public
---

## Summary
Delivered thread-scoped project chat model and reasoning effort controls. Conversation snapshots now persist `model` and `reasoning_effort`, new or unset threads resolve values from Global Settings in the project chat UI, and subsequent settings updates or chat turns send the selected values through the backend to Codex app-server. Blank reasoning effort remains a supported "use default" value and is omitted from `turn/start`.

## Validation
Ran `uv run pytest -q`.

Result: 952 passed in 12.44s.

## Shipped Changes
- Extended conversation state, repository serialization, workspace API request models, and project chat service handling for persisted model and normalized reasoning effort.
- Added `/workspace/api/projects/chat-models`, backed by Codex app-server `model/list`, with normalized model display/default and reasoning effort metadata.
- Carried `reasoning_effort` through prepared chat turns, chat sessions, and Codex app-server `turn/start` requests, including omission for blank effort.
- Added compact model and reasoning effort selectors to the project chat composer, with model metadata loading, Global Settings seeding, per-thread display, metadata-aware effort options, and fallback model/effort options.
- Updated frontend API/view-model/composer types and tests, plus backend API/service and Codex app client tests covering persistence, forwarding, validation, metadata parsing, and blank effort behavior.
