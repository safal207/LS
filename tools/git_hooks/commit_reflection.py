#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from agent.cognition import CognitiveTransaction, CreationFeedbackLayer

AGENT_ID = os.getenv("AGENT_ID", "local_agent")
MICRO_PAYOUT_CT = Decimal(os.getenv("MICRO_PAYOUT_CT", "0.5"))
PAYOUT_THRESHOLD_IMPACT = float(os.getenv("PAYOUT_THRESHOLD_IMPACT", "0.1"))
PROJECT_TREASURY = os.getenv("PROJECT_TREASURY", "project_treasury")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
CTL_ENDPOINT = os.getenv("CTL_ENDPOINT")
LOG_DIR = os.getenv("REFLECTION_LOG_DIR", "logs")
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)


def _run_git(cmd: list[str], cwd: str | None = None) -> str:
    proc = subprocess.run(["git", *cmd], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(cmd)} failed: {proc.stderr.strip()}")
    return proc.stdout


def _load_env_file() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _load_cel_types() -> tuple[type[Any] | None, type[Any] | None]:
    try:
        module = importlib.import_module("python.modules.cel.wallet_api")
    except Exception:
        return None, None
    return getattr(module, "CELWalletAPI", None), getattr(module, "TransferRequest", None)


def last_commit() -> dict[str, Any]:
    commit_hash = _run_git(["rev-parse", "HEAD"]).strip()
    message = _run_git(["show", "-s", "--format=%B", "HEAD"]).strip()
    numstat = _run_git(["show", "--numstat", "--format=", "HEAD"])

    files: list[str] = []
    insertions = 0
    deletions = 0
    files_changed = 0

    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        ins, dels, path = parts[0], parts[1], parts[2]
        ins_i = int(ins) if ins.isdigit() else 0
        dels_i = int(dels) if dels.isdigit() else 0
        insertions += ins_i
        deletions += dels_i
        files.append(path)
        files_changed += 1

    return {
        "hash": commit_hash,
        "message": message,
        "files_changed": files_changed,
        "insertions": insertions,
        "deletions": deletions,
        "files": files,
    }


def is_merge(msg: str) -> bool:
    lowered = msg.lower()
    return any(token in lowered for token in ("merge", "revert", "merge branch"))


def heuristics_score(files_changed: int, insertions: int, deletions: int) -> dict[str, Any]:
    impact = min(1.0, (insertions + deletions) / 200.0 + files_changed * 0.02)
    return {
        "impact": round(impact, 4),
        "files_changed": files_changed,
        "insertions": insertions,
        "deletions": deletions,
    }


def compute_accuracy(msg: str) -> float:
    base = 0.60
    lowered = msg.lower()
    if any(token in lowered for token in ("fix", "bug", "resolved", "test", "passed")):
        base += 0.25
    if any(token in lowered for token in ("refactor", "docs", "typo", "style")):
        base += 0.10
    return round(min(1.0, base), 4)


def append_ctl_event(event: dict[str, Any]) -> None:
    if CTL_ENDPOINT:
        try:
            requests_module = importlib.import_module("requests")
            response = requests_module.post(CTL_ENDPOINT, json=event, timeout=5)
            response.raise_for_status()
            return
        except Exception:
            pass

    path = Path(LOG_DIR) / "ctl_events.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def maybe_telegram_notify(text: str) -> None:
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return
    try:
        requests_module = importlib.import_module("requests")
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        requests_module.post(url, json={"chat_id": TG_CHAT_ID, "text": text}, timeout=3)
    except Exception:
        pass


def perform_payout_if_needed(metrics: dict[str, Any], commit: dict[str, Any]) -> dict[str, Any]:
    receipt_info: dict[str, Any] = {"payout": "0", "tx_ref": None, "status": "no_payout"}
    if metrics["impact"] <= PAYOUT_THRESHOLD_IMPACT:
        receipt_info["status"] = "low_impact"
        return receipt_info

    cel_wallet_api, transfer_request = _load_cel_types()
    if cel_wallet_api is None or transfer_request is None:
        receipt_info["status"] = "cel_unavailable"
        return receipt_info

    wallet = cel_wallet_api(append_ctl_event=append_ctl_event)
    amount = (MICRO_PAYOUT_CT * Decimal(str(metrics["impact"]))).quantize(Decimal("0.000001"))
    trace_id = f"trace_commit_{commit['hash'][:12]}"
    proposal_id = f"commit:{commit['hash'][:8]}"

    try:
        receipt = wallet.transfer(
            transfer_request(
                trace_id=trace_id,
                proposal_id=proposal_id,
                from_agent_id=PROJECT_TREASURY,
                to_agent_id=AGENT_ID,
                amount_ct=amount,
            )
        )
        receipt_info.update({"payout": str(receipt.amount_ct), "tx_ref": receipt.tx_ref, "status": "paid"})
    except Exception as exc:
        receipt_info.update({"status": "payout_failed", "error": str(exc)})

    return receipt_info


def make_ctl_event_from_feedback(feedback: dict[str, Any], commit: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": f"evt_{commit['hash'][:12]}",
        "trace_id": f"trace_commit_{commit['hash'][:12]}",
        "event_type": "micro_creation_reward",
        "ts": int(time.time()),
        "producer": "commit_reflection_hook",
        "schema_version": "1.0",
        "signature": "ed25519:unsigned-local",
        "data": {
            "commit_hash": commit["hash"],
            "agent_id": AGENT_ID,
            "micro_reward": feedback.get("micro_reward"),
            "quality_score": feedback.get("quality_score"),
            "contribution_score": feedback.get("contribution_score"),
        },
    }


def _feedback_to_dict(feedback_obj: Any) -> dict[str, Any]:
    if is_dataclass(feedback_obj):
        return asdict(feedback_obj)
    return dict(feedback_obj)


def main(argv: list[str] | None = None) -> int:
    _ = argv
    _load_env_file()

    try:
        commit = last_commit()
    except Exception as exc:
        print(json.dumps({"status": "git_error", "error": str(exc)}), flush=True)
        return 1

    if is_merge(commit["message"]):
        print(json.dumps({"status": "skipped_merge", "commit": commit["hash"]}, ensure_ascii=False))
        return 0

    metrics = heuristics_score(commit["files_changed"], commit["insertions"], commit["deletions"])
    metrics["accuracy"] = compute_accuracy(commit["message"])

    tx = CognitiveTransaction.create(actor=AGENT_ID, action="code_commit", payload={**commit, "metrics": metrics})
    cfl = CreationFeedbackLayer()
    feedback_obj = cfl.process_micro_step(tx, quality_score=metrics["accuracy"])
    feedback = _feedback_to_dict(feedback_obj) if feedback_obj else None

    payout = perform_payout_if_needed(metrics, commit)

    if feedback:
        ctl_event = make_ctl_event_from_feedback(feedback, commit)
        append_ctl_event(ctl_event)

    out = {
        "status": "success" if payout.get("status") == "paid" else payout.get("status"),
        "commit_hash": commit["hash"],
        "message": commit["message"].splitlines()[0] if commit["message"] else "",
        "metrics": metrics,
        "feedback": feedback,
        "payout": payout,
        "creation_score": cfl.creation_score,
    }

    print(json.dumps(out, ensure_ascii=False, indent=2))
    short = (
        f"Commit {commit['hash'][:8]} — status: {out['status']}, "
        f"impact={metrics['impact']}, payout={out['payout']['payout']}"
    )
    maybe_telegram_notify(short)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
