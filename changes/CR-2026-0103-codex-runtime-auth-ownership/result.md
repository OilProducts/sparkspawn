# Codex Runtime Auth Ownership — Result

Implemented manually.

- `spark-agent-adapter/src/codex_app_server.rs`: `build_codex_runtime_environment`
  seeds `auth.json` into the runtime codex home only when none exists there;
  an existing runtime credential file is never overwritten by the host copy.
  `config.toml` seeding and the standard-service-tier normalization are
  unchanged.
- Control-plane request timeout raised from 15s to 60s (`REQUEST_TIMEOUT`).
- Contract test `runtime_environment_never_overwrites_an_existing_runtime_auth_file`
  added alongside the existing first-launch seeding test, which still passes.

Operational note: after this lands, giving Spark its own codex session is
`CODEX_HOME=$SPARK_HOME/runtime/codex/.codex codex login`. The existing
runtime `auth.json` currently equals the host copy byte-for-byte (the seeding
overwrote the Aug 27 login), so that login should be repeated once after the
desktop is rebuilt.
