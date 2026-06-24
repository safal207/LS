#!/usr/bin/env python3
"""CLI adapter from Outcome Verification to VerifiedEpisode v0.2."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from ovc_episode_builder import build
from ovc_episode_checks import run
from ovc_episode_policy import choose

def evaluate(case):
    ovc,bindings,learning,lifecycle,eid,checks,faults=run(case)
    verdict,reason=choose(faults)
    episode=build(ovc,bindings,learning,lifecycle,eid) if verdict=="WRITE_CANDIDATE" else None
    return {
      "fixture_id":case.get("fixture_id","unknown"),
      "adapter_version":"ovc-to-verified-episode-v0.1",
      "verdict":verdict,"reason_code":reason,"episode":episode,
      "execution_authorized":False,"retroactive_authorization_created":False,
      "identity_update_applied":False,"downstream_learning_gate_required":True,
      "checks":checks,
    }

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input",type=Path)
    parser.add_argument("--check-expected",action="store_true")
    args=parser.parse_args()
    payload=json.loads(args.input.read_text(encoding="utf-8"))
    results=[];failures=[]
    for case in payload.get("cases",[payload]):
        result=evaluate(case);results.append(result);expected=case.get("expected",{})
        if args.check_expected and (result["verdict"]!=expected.get("verdict") or result["reason_code"]!=expected.get("reason_code")):
            failures.append({"fixture_id":case.get("fixture_id"),"expected":expected,"actual":{"verdict":result["verdict"],"reason_code":result["reason_code"]}})
    print(json.dumps({"results":results,"failures":failures},indent=2,sort_keys=True))
    return 1 if failures else 0

if __name__=="__main__":
    raise SystemExit(main())
