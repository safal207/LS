#!/usr/bin/env python3
"""Run the GitHub merge preflight without network or GitHub side effects."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from github_merge_preflight_core_v0_1 import PreflightError, envelope, evaluate, validate_input

GATEWAY_PATH = TOOLS / "review_decision_gateway_v0_1.py"
_spec = importlib.util.spec_from_file_location("merge_preflight_gateway", GATEWAY_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot import gateway from {GATEWAY_PATH}")
gateway = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = gateway
_spec.loader.exec_module(gateway)


def run(value: Any) -> dict[str, Any]:
    validated = None
    try:
        validated = validate_input(value)
        if validated["gateway_url"] != "in-process://review-decision-gateway-v0.1":
            raise PreflightError("NON_LOCAL_GATEWAY", "v0.1 accepts only the in-process gateway")
        request_id = "merge-preflight-" + validated["binding_digest"][:24]
        _status, response = gateway.ReviewDecisionGateway().project(validated["approval"], request_id)
        return evaluate(value, response, request_id)
    except PreflightError as exc:
        return envelope(validated, "BLOCK", exc.code, detail=exc.detail)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    args = parser.parse_args()
    if args.input:
        value = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        value = json.load(sys.stdin)
    result = run(value)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"] == "ALLOW_CLAIM" else 2


if __name__ == "__main__":
    raise SystemExit(main())
