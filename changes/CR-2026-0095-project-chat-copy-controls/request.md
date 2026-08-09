# Project Chat Copy Controls

## Summary

Add project-chat-only copy controls at two scopes:

- Every user message and completed assistant response copies its full raw text/Markdown.
- Every fenced code block inside rendered Markdown copies only that block’s code.

Streaming assistant responses do not expose response-level copy until complete. Inline code does not receive its own button. No backend, persistence, or API changes are required.

## Implementation Changes

- Add a small reusable transcript copy button using `navigator.clipboard.writeText`.
  - Use an icon button with accessible `aria-label`/tooltip text.
  - Replace the copy icon with a check briefly after success.
  - Show compact, accessible failure feedback when clipboard access is unavailable or writing fails.
  - Keep copied/error state local to each button so one control does not affect another.

- Extend the shared `MessageRow` interface with an opt-in copy capability.
  - Enable it from project conversation history only, avoiding unintended changes to Run transcripts.
  - Show it for every user message.
  - Show it for assistant messages only when `status === 'complete'`.
  - Copy the underlying `entry.content`, preserving raw Markdown rather than copying rendered DOM text.
  - Do not add copy controls to thinking, system, tool-call, or failed/streaming placeholder rows.

- Extend `ProjectConversationMarkdown` with an opt-in code-block copy mode.
  - Enable it for Markdown rendered in project chat, including completed assistant messages and proposed plans.
  - Wrap fenced code blocks in a positioned container with a copy button.
  - Extract the code block’s exact textual children, excluding the Markdown fence and language marker.
  - Preserve existing wrapping, memoization, and Markdown rendering behavior.
  - Leave inline code unchanged.
  - Keep other consumers—Runs results/questions and artifact views—unchanged unless they explicitly opt in later.

## Tests

- Message history tests:
  - Every user message has a copy button and copies its exact content.
  - A completed assistant response has a copy button and copies raw Markdown.
  - Streaming and failed assistant responses do not have response-level copy buttons.
  - Thinking and system rows remain unchanged.
  - Copy success changes the accessible state briefly.
  - Clipboard rejection produces accessible failure feedback.

- Markdown renderer tests:
  - Each fenced code block receives its own copy button.
  - Multiple code blocks copy independently.
  - Copied text excludes fences and language metadata while preserving code whitespace/newlines.
  - Inline code does not receive a copy button.
  - The opt-in flag prevents copy controls in existing non-chat consumers.

- Run the focused frontend component tests, then the frontend typecheck/test command used by the repository.

## Assumptions

- “Any Markdown/code rendered” means full-message copying plus per-fenced-code-block copying, not separate buttons on paragraphs, headings, lists, or inline code.
- This request applies only to project chat; shared Runs and artifact surfaces should not change.
- Proposed plans count as project-chat Markdown and receive per-code-block controls, while their card-level content is not treated as a top-level assistant response.
- Browser clipboard failure is reported in place; no deprecated DOM-based clipboard fallback is added.
