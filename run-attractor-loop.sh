#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECKLIST_FILE="$ROOT_DIR/ui-implementation-checklist.md"
MAX_ITERATIONS="${MAX_ITERATIONS:-100}"
STALL_LIMIT="${STALL_LIMIT:-3}"
CODEX_SANDBOX="${CODEX_SANDBOX:-danger-full-access}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --max-iterations N      Maximum loop iterations (default: $MAX_ITERATIONS)
  --stall-limit N         Stop after N non-progress iterations (default: $STALL_LIMIT)
  -h, --help              Show this help text

Environment overrides:
  MAX_ITERATIONS, STALL_LIMIT, CODEX_SANDBOX
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-iterations)
      MAX_ITERATIONS="$2"
      shift 2
      ;;
    --stall-limit)
      STALL_LIMIT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! command -v codex >/dev/null 2>&1; then
  echo "error: 'codex' CLI not found in PATH" >&2
  exit 1
fi

if [[ ! -f "$CHECKLIST_FILE" ]]; then
  echo "error: checklist file not found: $CHECKLIST_FILE" >&2
  exit 1
fi

count_unchecked() {
  rg -n '^\s*-\s*\[ \]' "$CHECKLIST_FILE" | wc -l | tr -d ' '
}

count_unchecked_active() {
  awk '
    BEGIN { in_deferred = 0; c = 0 }
    /^## Deferred Tasks/ { in_deferred = 1 }
    in_deferred == 0 && $0 ~ /^[[:space:]]*-[[:space:]]*\[ \]/ { c++ }
    END { print c + 0 }
  ' "$CHECKLIST_FILE"
}

count_unchecked_deferred() {
  awk '
    BEGIN { in_deferred = 0; c = 0 }
    /^## Deferred Tasks/ { in_deferred = 1; next }
    in_deferred == 1 && $0 ~ /^[[:space:]]*-[[:space:]]*\[ \]/ { c++ }
    END { print c + 0 }
  ' "$CHECKLIST_FILE"
}

checklist_hash() {
  shasum "$CHECKLIST_FILE" | awk '{print $1}'
}

extract_evaluator_verdict() {
  local log_file="$1"
  local verdict
  verdict="$(
    awk '
      function ltrim(s) { sub(/^[[:space:]]+/, "", s); return s }
      function rtrim(s) { sub(/[[:space:]]+$/, "", s); return s }
      function trim(s) { return rtrim(ltrim(s)) }
      {
        line = tolower($0)
        gsub(/\r/, "", line)
        gsub(/`/, "", line)
        gsub(/\*\*/, "", line)
        gsub(/^[[:space:]]*[-*][[:space:]]*/, "", line)
        if (line ~ /^evaluator_verdict[[:space:]]*:/) {
          value = line
          sub(/^evaluator_verdict[[:space:]]*:[[:space:]]*/, "", value)
          value = trim(value)
          if (index(value, "|") > 0) {
            next
          }
          sub(/[[:space:]].*$/, "", value)
          gsub(/[^a-z-].*$/, "", value)
          if (value != "") {
            parsed = value
          }
        }
      }
      END {
        if (parsed != "") {
          print parsed
        }
      }
    ' "$log_file"
  )"
  case "$verdict" in
    pass|fail|needs-human) ;;
    *) verdict="" ;;
  esac
  if [[ -z "${verdict:-}" ]]; then
    verdict="unknown"
  fi
  echo "$verdict"
}

extract_checklist_status_update() {
  local log_file="$1"
  local status
  status="$(
    awk '
      function ltrim(s) { sub(/^[[:space:]]+/, "", s); return s }
      function rtrim(s) { sub(/[[:space:]]+$/, "", s); return s }
      function trim(s) { return rtrim(ltrim(s)) }
      {
        line = tolower($0)
        gsub(/\r/, "", line)
        gsub(/`/, "", line)
        gsub(/\*\*/, "", line)
        gsub(/^[[:space:]]*[-*][[:space:]]*/, "", line)
        if (line ~ /^checklist_status_update[[:space:]]*:/) {
          value = line
          sub(/^checklist_status_update[[:space:]]*:[[:space:]]*/, "", value)
          value = trim(value)
          if (index(value, "|") > 0) {
            next
          }
          sub(/[[:space:]].*$/, "", value)
          gsub(/[^a-z-].*$/, "", value)
          if (value != "") {
            parsed = value
          }
        }
      }
      END {
        if (parsed != "") {
          print parsed
        }
      }
    ' "$log_file"
  )"
  case "$status" in
    checked|unchecked|deferred) ;;
    *) status="" ;;
  esac
  if [[ -z "${status:-}" ]]; then
    status="unknown"
  fi
  echo "$status"
}

report_stop_and_restore_state() {
  local exit_code="$1"
  local reason="$2"
  local checklist_snapshot="$3"
  local iteration_log="$4"
  local head_before="$5"
  local head_after="$6"

  if [[ -n "$head_before" && -n "$head_after" && "$head_before" != "$head_after" ]]; then
    rm -f "$checklist_snapshot"
    echo "Stopping: $reason" >&2
    echo "New commit detected during iteration ($head_before -> $head_after); checklist snapshot NOT restored." >&2
  else
    cp "$checklist_snapshot" "$CHECKLIST_FILE"
    rm -f "$checklist_snapshot"
    echo "Stopping: $reason" >&2
    echo "Checklist reverted to pre-iteration snapshot." >&2
  fi
  echo "Iteration log retained at: $iteration_log" >&2
  exit "$exit_code"
}

read -r -d '' ACTIVE_PROMPT <<'EOF' || true
Use ui-implementation-checklist.md and pick the next unchecked item.

Workflow:
1) Determine if the item is ready to be worked now by scanning code/tests/spec. If not ready, move it to a “Deferred Tasks” section at the end of the checklist and explain why in one sentence.
2) If ready, do strict test-first:
   - Add/update tests for only this item.
   - Run `just test` (use pytest, not unittest entrypoints).
   - Confirm red, then implement minimal code to turn green.
   - If your changes touch `frontend/`, run `just ui-smoke` to generate screenshots in `frontend/artifacts/ui-smoke/`.
3) Keep scope narrow. No unrelated refactors.
4) Checklist gate rules (required):
   - Keep the selected checklist item unchecked (`[ ]`) until evaluator approval is known.
   - Only mark the item checked (`[x]`) if evaluator verdict is `pass`.
   - If evaluator verdict is `fail` or `needs-human`, keep item unchecked and add/update a one-sentence blocker note.
   - If you marked `[x]` before evaluation, revert it back to `[ ]` before commit unless verdict is `pass`.
5) After implementation, spawn a sub-agent to evaluate whether the item is tested and implemented in the spirit of ui-spec.md.
   - If your changes touched `frontend/`, you MUST provide screenshot paths from `frontend/artifacts/ui-smoke/` to the sub-agent and ask for visual QA findings from those images.
   - Include sub-agent verdict and evidence in your report.
6) Commit your changes with a clear message. If there are unrelated untracked files, do not include them.

Output:
- Selected item and readiness decision
- Test changes
- Code changes
- Commands run + outcomes
- If `frontend/` changed: UI smoke result and screenshot paths under `frontend/artifacts/ui-smoke/`
- Sub-agent verdict (verbatim). If `frontend/` changed, this verdict must include screenshot-based visual QA findings.
- EVALUATOR_VERDICT: pass | fail | needs-human (plain token, no backticks)
- CHECKLIST_STATUS_UPDATE: checked | unchecked | deferred (plain token, no backticks)
- Difficulties and workflow improvements
- Commit hash
EOF

read -r -d '' DEFERRED_PROMPT <<'EOF' || true
Use ui-implementation-checklist.md and reassess the next unchecked item under the “Deferred Tasks” section only.

Workflow:
1) Reassess readiness by scanning code/tests/spec.
2) Choose one action:
   - If already implemented/tested in spirit of ui-spec.md, mark that Deferred item as `[x]` with a short verification note.
   - If now ready and missing, do strict test-first for only that item (red -> minimal green), then mark it `[x]`.
   - If still blocked, keep it unchecked and tighten its one-sentence defer reason.
   - If your changes touch `frontend/`, run `just ui-smoke` to generate screenshots in `frontend/artifacts/ui-smoke/`.
3) Keep scope narrow. No unrelated refactors.
4) Checklist gate rules (required):
   - Keep the selected checklist item unchecked (`[ ]`) until evaluator approval is known.
   - Only mark the item checked (`[x]`) if evaluator verdict is `pass`.
   - If evaluator verdict is `fail` or `needs-human`, keep item unchecked and tighten the defer blocker reason.
   - If you marked `[x]` before evaluation, revert it back to `[ ]` before commit unless verdict is `pass`.
5) Spawn a sub-agent to evaluate whether your action is correct in spirit of ui-spec.md.
   - If your changes touched `frontend/`, you MUST provide screenshot paths from `frontend/artifacts/ui-smoke/` to the sub-agent and ask for visual QA findings from those images.
   - Include verdict and evidence.
6) Commit changes with a clear message. If there are unrelated untracked files, do not include them.

Output:
- Selected deferred item and reassessment decision
- Action taken (`verified-existing` / `implemented-now` / `still-blocked`)
- Test changes
- Code/checklist changes
- Commands run + outcomes
- If `frontend/` changed: UI smoke result and screenshot paths under `frontend/artifacts/ui-smoke/`
- Sub-agent verdict (verbatim). If `frontend/` changed, this verdict must include screenshot-based visual QA findings.
- EVALUATOR_VERDICT: pass | fail | needs-human (plain token, no backticks)
- CHECKLIST_STATUS_UPDATE: checked | unchecked | deferred (plain token, no backticks)
- Difficulties and workflow improvements
- Commit hash
EOF

active_before="$(count_unchecked_active)"
deferred_before="$(count_unchecked_deferred)"
total_before=$((active_before + deferred_before))
hash_before="$(checklist_hash)"

if [[ "$total_before" -eq 0 ]]; then
  echo "Checklist already complete: $CHECKLIST_FILE"
  exit 0
fi

echo "Starting loop: active_unchecked=$active_before deferred_unchecked=$deferred_before total_unchecked=$total_before"
stalled_iterations=0

for ((i = 1; i <= MAX_ITERATIONS; i++)); do
  phase="active"
  prompt="$ACTIVE_PROMPT"
  if [[ "$active_before" -eq 0 && "$deferred_before" -gt 0 ]]; then
    phase="deferred"
    prompt="$DEFERRED_PROMPT"
  fi

  echo
  echo "=== Iteration $i ==="
  echo "Phase: $phase"
  echo "Before run: active_unchecked=$active_before deferred_unchecked=$deferred_before total_unchecked=$total_before"

  head_before="$(git -C "$ROOT_DIR" rev-parse HEAD 2>/dev/null || true)"
  checklist_snapshot="$(mktemp)"
  cp "$CHECKLIST_FILE" "$checklist_snapshot"
  iteration_log="$(mktemp)"
  if codex exec --sandbox "$CODEX_SANDBOX" -C "$ROOT_DIR" "$prompt" 2>&1 | tee "$iteration_log"; then
    codex_exit=0
  else
    codex_exit=$?
  fi
  head_after="$(git -C "$ROOT_DIR" rev-parse HEAD 2>/dev/null || true)"

  if [[ "$codex_exit" -ne 0 ]]; then
    report_stop_and_restore_state 8 "codex exec failed." "$checklist_snapshot" "$iteration_log" "$head_before" "$head_after"
  fi
  evaluator_verdict="$(extract_evaluator_verdict "$iteration_log")"
  checklist_status_update="$(extract_checklist_status_update "$iteration_log")"

  active_after="$(count_unchecked_active)"
  deferred_after="$(count_unchecked_deferred)"
  total_after=$((active_after + deferred_after))
  hash_after="$(checklist_hash)"
  echo "After run: active_unchecked=$active_after deferred_unchecked=$deferred_after total_unchecked=$total_after"
  echo "Evaluator verdict: $evaluator_verdict"
  echo "Checklist status update: $checklist_status_update"

  if [[ "$evaluator_verdict" == "unknown" ]]; then
    report_stop_and_restore_state 6 "missing required machine-readable EVALUATOR_VERDICT output." "$checklist_snapshot" "$iteration_log" "$head_before" "$head_after"
  fi

  if [[ "$checklist_status_update" == "unknown" ]]; then
    report_stop_and_restore_state 7 "missing required machine-readable CHECKLIST_STATUS_UPDATE output." "$checklist_snapshot" "$iteration_log" "$head_before" "$head_after"
  fi

  if [[ "$total_after" -lt "$total_before" && "$evaluator_verdict" != "pass" ]]; then
    report_stop_and_restore_state 4 "checklist unchecked count decreased without evaluator pass verdict. Expected EVALUATOR_VERDICT: pass when marking an item complete." "$checklist_snapshot" "$iteration_log" "$head_before" "$head_after"
  fi

  if [[ "$checklist_status_update" == "checked" && "$evaluator_verdict" != "pass" ]]; then
    report_stop_and_restore_state 5 "implementor reported CHECKLIST_STATUS_UPDATE=checked with non-pass evaluator verdict." "$checklist_snapshot" "$iteration_log" "$head_before" "$head_after"
  fi

  rm -f "$checklist_snapshot"
  rm -f "$iteration_log"

  if [[ "$total_after" -eq 0 ]]; then
    echo "Checklist complete."
    exit 0
  fi

  made_progress=0
  if [[ "$total_after" -lt "$total_before" ]]; then
    made_progress=1
  elif [[ "$hash_after" != "$hash_before" ]]; then
    # Deferred reassessment can legitimately improve notes/actionability
    # without reducing unchecked count immediately.
    made_progress=1
  fi

  if [[ "$made_progress" -eq 0 ]]; then
    stalled_iterations=$((stalled_iterations + 1))
    echo "No progress detected ($stalled_iterations/$STALL_LIMIT stall limit)."
  else
    stalled_iterations=0
  fi

  if [[ "$stalled_iterations" -ge "$STALL_LIMIT" ]]; then
    echo "Stopping: no checklist progress for $STALL_LIMIT consecutive iteration(s)." >&2
    exit 2
  fi

  active_before="$active_after"
  deferred_before="$deferred_after"
  total_before="$total_after"
  hash_before="$hash_after"
done

echo "Stopping: reached MAX_ITERATIONS=$MAX_ITERATIONS with work still remaining." >&2
exit 3
