# Project Owner Workflow

## Goal

Verify that a project owner can work inside a single project-scoped Home workflow from conversation through flow-run request review and execution follow-through.

## Preconditions

1. An active project is selected.
2. Project chat is available and backed by the chat runtime.
3. The project has a usable flow for follow-on execution when needed.

## Workflow

1. Open the Home area.
2. Select or create a project conversation thread.
3. Send a project-scoped message in chat.
4. Observe streaming assistant activity and any inline tool calls.
5. Review any proposed flow-run request card that appears.
6. Approve or reject the flow-run request explicitly.
7. If approved, observe launch progress in the workflow event log.
8. If a direct launch is used instead, confirm the conversation records the launched run.
9. Continue toward build execution when supported by the selected flow.

## Expected Outcomes

- Threaded project chat remains scoped to the active project.
- Tool activity and assistant output are visible in the conversation timeline.
- Flow-run requests are explicit review artifacts, not silent launches.
- Direct launches remain visible in the same conversation context.
- Workflow/system progress stays in the event log rather than polluting the chat timeline.
