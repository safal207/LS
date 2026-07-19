#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 https://your-public-alibaba-cloud-service.example" >&2
  exit 2
fi

service_url="${1%/}"
workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

health_file="$workdir/health.json"
assessment_file="$workdir/assessment.json"

curl --fail --silent --show-error \
  "$service_url/healthz" \
  --output "$health_file"

curl --fail --silent --show-error \
  "$service_url/api/evaluate" \
  --header 'content-type: application/json' \
  --data '{
    "actor": "deployment-proof-agent",
    "action": "Generate read-only deployment verification report",
    "resource": "hackathon demo service",
    "context": "Public verification request after Alibaba Cloud deployment",
    "requested_effect": "Return an advisory assessment without executing an external action",
    "metadata": {
      "reversible": true,
      "has_test_evidence": true,
      "user_consent": true
    }
  }' \
  --output "$assessment_file"

python - "$health_file" "$assessment_file" <<'PY'
import json
import sys
from pathlib import Path

health = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assessment = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))

assert health.get("status") == "ok", health
assert assessment.get("qwen", {}).get("status") == "COMPLETED", assessment
assert assessment.get("execution", {}).get("status") == "NOT_EXECUTED", assessment
assert assessment.get("execution", {}).get("authority") == "advisory_only", assessment

print(json.dumps({
    "health": health,
    "assessment": assessment,
}, indent=2, ensure_ascii=False))
PY
