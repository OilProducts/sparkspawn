#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECKLIST_FILE="$ROOT_DIR/ui-implementation-checklist.md"
CODEX_SANDBOX="${CODEX_SANDBOX:-danger-full-access}"
CODEX_MODEL="gpt-5.3-codex-spark"
MAX_ITEMS=0
ONLY_ID=""
FAIL_ON_SUSPECT=0
OUT_DIR=""

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Audit all checked checklist items in ui-implementation-checklist.md by running
one evaluator pass per checked item and writing a machine-readable report.

Options:
  --checklist PATH        Checklist file path (default: $CHECKLIST_FILE)
  --output-dir PATH       Report directory (default: artifacts/checklist-completion-audit/<timestamp>)
  --max-items N           Limit number of checked items audited (default: all)
  --only-id ID            Audit only one checklist item id (example: 6.2-01)
  --sandbox MODE          codex sandbox mode (default: \$CODEX_SANDBOX or danger-full-access)
  --fail-on-suspect       Exit non-zero if any item is fail/needs-human
  -h, --help              Show this help text
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --checklist)
      CHECKLIST_FILE="$2"
      shift 2
      ;;
    --output-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    --max-items)
      MAX_ITEMS="$2"
      shift 2
      ;;
    --only-id)
      ONLY_ID="$2"
      shift 2
      ;;
    --sandbox)
      CODEX_SANDBOX="$2"
      shift 2
      ;;
    --fail-on-suspect)
      FAIL_ON_SUSPECT=1
      shift
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

if ! [[ "$MAX_ITEMS" =~ ^[0-9]+$ ]]; then
  echo "error: --max-items must be a non-negative integer" >&2
  exit 1
fi

if [[ -z "$OUT_DIR" ]]; then
  run_ts="$(date +%Y%m%d-%H%M%S)"
  OUT_DIR="$ROOT_DIR/artifacts/checklist-completion-audit/$run_ts"
fi

mkdir -p "$OUT_DIR/logs"

ITEMS_FILE="$(mktemp)"
FILTERED_ITEMS_FILE="$(mktemp)"
trap 'rm -f "$ITEMS_FILE" "$FILTERED_ITEMS_FILE"' EXIT

awk '
  $0 ~ /^- \[x\] \[[^]]+\] / {
    line = NR
    item_id = $0
    desc = $0

    sub(/^- \[x\] \[/, "", item_id)
    sub(/\].*$/, "", item_id)
    sub(/^- \[x\] \[[^]]+\] /, "", desc)

    gsub(/\t/, " ", desc)
    print line "\t" item_id "\t" desc
  }
' "$CHECKLIST_FILE" > "$ITEMS_FILE"

if [[ -n "$ONLY_ID" ]]; then
  awk -F'\t' -v only_id="$ONLY_ID" '$2 == only_id { print }' "$ITEMS_FILE" > "$FILTERED_ITEMS_FILE"
else
  cp "$ITEMS_FILE" "$FILTERED_ITEMS_FILE"
fi

if [[ "$MAX_ITEMS" -gt 0 ]]; then
  head -n "$MAX_ITEMS" "$FILTERED_ITEMS_FILE" > "$FILTERED_ITEMS_FILE.tmp"
  mv "$FILTERED_ITEMS_FILE.tmp" "$FILTERED_ITEMS_FILE"
fi

item_count="$(wc -l < "$FILTERED_ITEMS_FILE" | tr -d ' ')"
if [[ "$item_count" -eq 0 ]]; then
  echo "No checked items matched the selected filter."
  exit 0
fi

RESULTS_TSV="$OUT_DIR/results.tsv"
SUMMARY_MD="$OUT_DIR/summary.md"
cp "$FILTERED_ITEMS_FILE" "$OUT_DIR/checked-items.tsv"

printf "line\titem_id\tverdict\tconfidence\tsuspect\treason\tevidence\n" > "$RESULTS_TSV"

echo "Auditing $item_count checked item(s)..."

while IFS=$'\t' read -r line item_id desc; do
  item_log="$OUT_DIR/logs/${line}-${item_id}.log"

  read -r -d '' prompt <<EOF || true
Audit checklist item completion in this repository. Do not edit any files.

Checklist:
- File: $CHECKLIST_FILE
- Line: $line
- Item ID: $item_id
- Claimed complete text: $desc

Evaluation requirements:
1) Determine whether this item is truly complete in spirit of ui-spec.md and current implementation/tests.
2) Use repository evidence (code, tests, docs). Run read-only commands/tests if needed.
3) If evidence is mixed/insufficient, return needs-human.
4) Never modify files.

Output exactly these lines:
AUDIT_ITEM_ID: $item_id
AUDIT_VERDICT: pass|fail|needs-human
AUDIT_CONFIDENCE: high|medium|low
AUDIT_REASON: <one concise sentence>
AUDIT_EVIDENCE: <semicolon-separated file paths and/or test ids>
EOF

  codex exec -m "$CODEX_MODEL" --sandbox "$CODEX_SANDBOX" -C "$ROOT_DIR" "$prompt" | tee "$item_log" >/dev/null

  verdict="$(rg -N -o 'AUDIT_VERDICT:\s*(pass|fail|needs-human)' "$item_log" | tail -n1 | awk -F': ' '{print $2}' || true)"
  confidence="$(rg -N -o 'AUDIT_CONFIDENCE:\s*(high|medium|low)' "$item_log" | tail -n1 | awk -F': ' '{print $2}' || true)"
  reason="$(rg -N '^AUDIT_REASON:' "$item_log" | tail -n1 | sed 's/^AUDIT_REASON:[[:space:]]*//' || true)"
  evidence="$(rg -N '^AUDIT_EVIDENCE:' "$item_log" | tail -n1 | sed 's/^AUDIT_EVIDENCE:[[:space:]]*//' || true)"

  if [[ -z "${verdict:-}" ]]; then
    verdict="needs-human"
  fi
  if [[ -z "${confidence:-}" ]]; then
    confidence="low"
  fi
  if [[ -z "${reason:-}" ]]; then
    reason="Missing machine-readable audit reason from evaluator output."
  fi
  if [[ -z "${evidence:-}" ]]; then
    evidence="(no evidence line returned)"
  fi

  reason="${reason//$'\t'/ }"
  evidence="${evidence//$'\t'/ }"
  reason="${reason//$'\n'/ }"
  evidence="${evidence//$'\n'/ }"

  suspect="no"
  if [[ "$verdict" != "pass" ]]; then
    suspect="yes"
  fi

  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$line" "$item_id" "$verdict" "$confidence" "$suspect" "$reason" "$evidence" >> "$RESULTS_TSV"

  echo "[$item_id] verdict=$verdict confidence=$confidence suspect=$suspect"
done < "$FILTERED_ITEMS_FILE"

total="$(awk 'NR>1 {c++} END {print c+0}' "$RESULTS_TSV")"
pass_count="$(awk -F'\t' 'NR>1 && $3=="pass" {c++} END {print c+0}' "$RESULTS_TSV")"
fail_count="$(awk -F'\t' 'NR>1 && $3=="fail" {c++} END {print c+0}' "$RESULTS_TSV")"
needs_human_count="$(awk -F'\t' 'NR>1 && $3=="needs-human" {c++} END {print c+0}' "$RESULTS_TSV")"
suspect_count="$(awk -F'\t' 'NR>1 && $5=="yes" {c++} END {print c+0}' "$RESULTS_TSV")"

{
  echo "# UI Checklist Completion Audit"
  echo
  echo "- Checklist: \`$CHECKLIST_FILE\`"
  echo "- Total audited: $total"
  echo "- pass: $pass_count"
  echo "- fail: $fail_count"
  echo "- needs-human: $needs_human_count"
  echo "- suspect checkmarks: $suspect_count"
  echo
  echo "| line | item_id | verdict | confidence | suspect | reason |"
  echo "|---:|---|---|---|---|---|"
  awk -F'\t' 'NR>1 { printf "| %s | %s | %s | %s | %s | %s |\n", $1, $2, $3, $4, $5, $6 }' "$RESULTS_TSV"
} > "$SUMMARY_MD"

echo
echo "Audit complete."
echo "Results TSV: $RESULTS_TSV"
echo "Summary MD:  $SUMMARY_MD"
echo "Raw logs:    $OUT_DIR/logs"

if [[ "$FAIL_ON_SUSPECT" -eq 1 && "$suspect_count" -gt 0 ]]; then
  exit 2
fi
