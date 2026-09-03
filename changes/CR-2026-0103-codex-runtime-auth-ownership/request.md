# Codex Runtime Auth Ownership

## Summary

Spark's codex adapter re-seeds `auth.json` from the host `~/.codex` into its
isolated runtime codex home on every app-server spawn whenever the two files
differ. That makes the runtime home and the user's own codex CLI share a
single OAuth refresh-token chain: whichever install refreshes second is
invalidated ("Your access token could not be refreshed because your refresh
token was already used"). It also silently overwrites a login performed
against the runtime `CODEX_HOME`, the documented way to give Spark its own
session. Separately, the adapter bounds every control-plane request at 15s,
which has proven too tight for first-reply work such as MCP server startup or
a token refresh.

## Implementation Changes

- Seed `auth.json` only when the runtime home has none. Once present, the
  runtime home owns its credentials; the host copy is never consulted again.
  `config.toml` seeding is unchanged.
- Raise the control-plane request timeout from 15s to 60s. The bound exists to
  catch a wedged app-server, not to race normal startup.

## Test Plan

- An existing runtime `auth.json` survives environment construction when the
  host copy differs; config is still seeded.
- First-launch seeding of a missing runtime `auth.json` is unchanged.

## Assumptions

- Fixing Spark's codex session is done with
  `CODEX_HOME=$SPARK_HOME/runtime/codex/.codex codex login`, never by copying
  files between homes.
