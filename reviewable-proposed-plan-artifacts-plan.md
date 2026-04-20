# Reviewable Proposed Plan Artifacts in Project Chat

## Summary

Turn Proposed Plan cards into first-class conversation artifacts with explicit review state.

- Each persisted Proposed Plan card becomes a reviewable artifact owned by the conversation and source turn that produced it
- Any unreviewed plan may be explicitly approved or disapproved
- Approval writes the approved plan to `changes/CR-<year>-<seq>-<slug>/request.md`, derives the CR directory from the plan title, and launches `implement-change-request` in the owning conversation
- Disapproval marks the artifact rejected and keeps it in history as an auditable outcome
- Approval and disapproval may include an optional review note
- Approving a plan does not change the conversation’s `chat_mode`

## Key Changes

- Add a dedicated Proposed Plan artifact model:
  - Persist a conversation-scoped record for each plan card with `conversation_id`, `source_turn_id`, `source_segment_id`, review status, optional review note, written file path, and launched run/flow-launch ids
  - Keep the existing `plan` segment for inline rendering, but attach it to the artifact so the card is an actionable object rather than bare markdown
  - Default artifact status to `pending_review`

- Add explicit review actions for plan artifacts:
  - `approve` writes the plan content to `changes/CR-.../request.md`, records the durable change-request path on the artifact, creates a conversation-scoped direct flow launch for `software-development/implement-change-request.dot`, and marks the artifact approved
  - `disapprove` marks the artifact rejected, stores the optional review note, and does not launch anything
  - Once reviewed, the artifact becomes locked: no further approve/disapprove actions for that plan

- Scope approval to the owning conversation, not ambient UI state:
  - The backend resolves launch scope from the artifact’s persisted `conversation_id`, not from the currently active conversation handle in the page
  - This ensures approving a plan always launches in the conversation that produced that plan card
  - Do not hardcode `faint-sky`; use the artifact’s owning conversation handle resolved from persisted conversation state

- Define deterministic file-writing behavior:
  - Use the top-level plan heading as the base filename
  - Strip markdown formatting, slugify to a filesystem-safe name, and write under `changes/` as `<slug>.md`
  - If no heading exists, fall back to a safe default like `proposed-plan.md`
  - If the filename already exists, append `-2`, `-3`, and so on
  - Store the final written path on the artifact for later display

- Update Project Chat UI for reviewable plan cards:
  - Show review controls on pending Proposed Plan cards: `Approve` and `Disapprove`
  - Include an optional short review-note input on the card
  - After approval, show compact artifact metadata on the card such as approved status, written file path, and launched run
  - After disapproval, show rejected status and optional note, with actions removed
  - Do not switch the conversation out of plan mode as part of approval

## Required Interfaces

- New conversation artifact type for Proposed Plans with fields for:
  - provenance: `conversation_id`, `source_turn_id`, `source_segment_id`
  - status: `pending_review` | `approved` | `rejected` | `launch_failed`
  - optional `review_note`
  - optional `written_change_request_path`
  - optional `flow_launch_id` and `run_id`

- New Project Chat review endpoint/action:
  - review a Proposed Plan artifact by artifact id and disposition
  - optional note payload
  - on approval, perform file write + flow launch atomically enough that persisted state reflects success or launch failure clearly

No automatic `chat_mode` changes are part of this feature.

## Test Plan

- Backend/service test: a generated Proposed Plan creates a reviewable artifact tied to the correct conversation, turn, and segment
- Backend/service test: approving a plan writes a markdown file with title-derived slug and collision handling
- Backend/service test: approving a plan launches `software-development/implement-change-request.dot` in the artifact’s owning conversation, not the ambient active conversation
- Backend/service test: approval records `written_change_request_path`, `flow_launch_id`, and `run_id` on the artifact
- Backend/service test: disapproval marks the artifact rejected and stores the optional note without launching
- Backend/service test: reviewed artifacts cannot be reviewed again
- Frontend rendering test: pending Proposed Plan cards show approve/disapprove controls and optional note input
- Frontend rendering test: approved cards show status plus file/run metadata and no review controls
- Frontend rendering test: rejected cards show rejected status and optional note and no review controls
- Regression test: approving a plan does not change `chat_mode`
- Full validation gate: `uv run pytest -q`

## Assumptions

- Any unreviewed Proposed Plan may be reviewed independently; review is not limited to the latest card
- Disapproval is terminal for that artifact and remains visible in history
- Review notes are optional for both approval and disapproval
- Approved plan output lives under `changes/` so the durable change record is visible in the repo without mixing with Spark runtime state
