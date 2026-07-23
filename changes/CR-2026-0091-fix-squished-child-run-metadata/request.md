# Fix Squished Child-Run Metadata

## Summary

Restore the run-list row’s non-wrapping layout so nested child cards reserve usable width for metadata while keeping the status badge aligned on the right.

## Implementation

- In `RunList.tsx`, remove wrapping from the title/status flex row.
- Make the consolidated metadata line truncate within its available width instead of wrapping into a narrow column.
- Preserve child indentation, root-run metadata, status badges, and all existing responsive behavior.

## Test Plan

- Extend the existing child-run test to verify the child row uses a non-wrapping title/status layout and a truncating metadata line.
- Run the focused `RunList` unit test, then the frontend unit suite if the focused test passes.

## Interfaces and Assumptions

- No API, type, data-model, or dependency changes.
- Long metadata is intentionally truncated in the compact sidebar; its full identifiers remain available through existing titles and the run details view.
