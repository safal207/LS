#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
GATE="$ROOT_DIR/tools/build_week_trust_gate.py"
POLICY="$ROOT_DIR/build-week/policy/trust-policy.json"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  printf 'Build Week demo error: Python interpreter not found: %s\n' "$PYTHON_BIN" >&2
  exit 2
fi

scenarios=(
  "stale approval|stale-approval.json|BLOCKED|STALE_APPROVAL"
  "spoofed reviewer|spoofed-reviewer.json|BLOCKED|UNTRUSTED_REVIEWER"
  "required lane absent|required-check-not-run.json|BLOCKED|REQUIRED_LANE_NOT_RUN"
  "current-head review|trusted-current-head.json|TRUSTED|ALL_REQUIRED_EVIDENCE_VALID"
)

printf 'LS Build Week demo — attack → detect → block\n\n'

failures=0
scenario_number=0
for scenario in "${scenarios[@]}"; do
  scenario_number=$((scenario_number + 1))
  IFS='|' read -r label fixture_name expected_verdict expected_reason <<<"$scenario"
  fixture="$ROOT_DIR/build-week/demo/$fixture_name"

  if report="$("$PYTHON_BIN" "$GATE" "$fixture" --policy "$POLICY" --format json --verify-expected 2>&1)"; then
    if parsed="$("$PYTHON_BIN" -c 'import json, sys; report = json.load(sys.stdin); print("{}\t{}".format(report["verdict"], report["reason_code"]))' <<<"$report")"; then
      IFS=$'\t' read -r verdict reason_code <<<"$parsed"
    else
      verdict="ERROR"
      reason_code="INVALID_REPORT"
    fi
  else
    exit_code=$?
    verdict="ERROR"
    reason_code="GATE_EXIT_${exit_code}"
    printf '%s\n' "$report" >&2
  fi

  printf 'Scenario %d: %-24s %-7s %s\n' "$scenario_number" "$label" "$verdict" "$reason_code"
  if [[ "$verdict" != "$expected_verdict" || "$reason_code" != "$expected_reason" ]]; then
    failures=$((failures + 1))
  fi
done

printf '\n'
if ((failures > 0)); then
  printf 'Demo result: FAILED — %d scenario(s) did not match the expected trust decision.\n' "$failures" >&2
  exit 1
fi

printf 'Demo result: 4/4 scenarios matched the expected trust decisions.\n'
