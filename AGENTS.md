## Test Execution Policy
- Always run tests with `uv run pytest`
- Before reporting completion of a code change, run the full suite with `uv run pytest -q` unless the user asks otherwise.
- For failure triage, prefer `uv run pytest -q -x --maxfail=1 <path-or-nodeid>` to get the first actionable error quickly.
