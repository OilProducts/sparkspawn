## Test Execution Policy
- Always run tests with `uv run pytest`
- Before reporting completion of a code change, run the full suite with `uv run pytest -q` unless the user asks otherwise.
- For failure triage, prefer `uv run pytest -q -x --maxfail=1 <path-or-nodeid>` to get the first actionable error quickly.
- Write tests against observable behavior through real interfaces (CLI output, API responses, UI behavior, filesystem effects, state transitions), not repository text.
- When a change replaces or removes a behavior, delete or rewrite tests for the old behavior unless backward compatibility is an explicit requirement.
- Do not add or keep tests that depend on source/prompt/doc/spec strings or deprecated details, or that would fail after harmless refactoring or rewording while behavior remains correct.

## UI Spec Guidance
- Figma answers: what should this look like?
- Spec answers: what should happen?
- Tests answer: does it actually do that?
