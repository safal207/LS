#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    def load_dotenv() -> bool:
        return False

try:
    from ls.cognition import CognitiveTransaction, CreationFeedbackLayer  # type: ignore
except Exception:  # pragma: no cover
    from agent.cognition import CognitiveTransaction  # type: ignore

    class CreationFeedbackLayer:
        """Fallback creation feedback layer with score accumulation."""

        def __init__(self) -> None:
            self.creation_score = 0.0

        def ingest_transaction(self, tx: Any) -> dict[str, float]:
            metrics = tx.payload.get("metrics", {}) if hasattr(tx, "payload") else {}
            impact = float(metrics.get("impact", 0.0))
            accuracy = float(metrics.get("accuracy", 0.0))
            delta = round(impact * (0.5 + accuracy / 2), 6)
            self.creation_score += delta
            return {"creation_score_delta": delta}

try:
    from ls.modules.cel import CELWalletAPI, TransferRequest  # type: ignore
except Exception:  # pragma: no cover
    try:
        from modules.cel import CELWalletAPI, TransferRequest  # type: ignore
    except Exception:  # pragma: no cover
        CELWalletAPI = None  # type: ignore
        TransferRequest = None  # type: ignore

load_dotenv()

LOG = logging.getLogger("commit_reflection")
logging.basicConfig(level=os.getenv("COMMIT_REFLECTION_LOG_LEVEL", "INFO"))

AGENT_ID = os.getenv("AGENT_ID", "agent_local_1")
MICRO_PAYOUT_CT = Decimal(os.getenv("MICRO_PAYOUT_CT", "0.5"))
PAYOUT_THRESHOLD_IMPACT = float(os.getenv("PAYOUT_THRESHOLD_IMPACT", "0.1"))
PROJECT_TREASURY = os.getenv("PROJECT_TREASURY", "project_treasury")
PROJECT_TREASURY_BALANCE_CT = Decimal(os.getenv("PROJECT_TREASURY_BALANCE_CT", "1000000"))
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
CTL_ENDPOINT = os.getenv("CTL_ENDPOINT")


@dataclass(frozen=True)
class CommitInfo:
    hash: str
    message: str
    files_changed: int
    insertions: int
    deletions: int
    files: list[str]


def run_git(args: list[str]) -> str:
    proc = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def last_commit() -> CommitInfo:
    commit_hash = run_git(["log", "-1", "--pretty=%H"])
    message = run_git(["log", "-1", "--pretty=%s"])
    files_raw = run_git(["diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash])
    files = [line for line in files_raw.splitlines() if line]

    numstat = run_git(["show", "--numstat", "--format=", "-1", commit_hash])
    insertions = 0
    deletions = 0
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            ins, dele = parts[0], parts[1]
            insertions += int(ins) if ins.isdigit() else 0
            deletions += int(dele) if dele.isdigit() else 0

    return CommitInfo(
        hash=commit_hash,
        message=message,
        files_changed=len(files),
        insertions=insertions,
        deletions=deletions,
        files=files,
    )


def is_merge(message: str) -> bool:
    lowered = message.lower()
    return bool(re.search(r"\b(merge|revert|merge branch)\b", lowered))


def heuristics_score(files_changed: int, insertions: int, deletions: int) -> dict[str, float | int]:
    impact = min(1.0, (insertions + deletions) / 200.0 + files_changed * 0.02)
    return {
        "impact": round(impact, 4),
        "files_changed": files_changed,
        "insertions": insertions,
        "deletions": deletions,
    }


def compute_accuracy(message: str) -> float:
    score = 0.60
    lowered = message.lower()
    if re.search(r"\b(fix|bug|resolved|test|passed)\b", lowered):
        score += 0.25
    if re.search(r"\b(refactor|docs|typo|style)\b", lowered):
        score += 0.10
    return round(min(1.0, score), 4)


def append_ctl_event_fallback(event: dict[str, Any]) -> None:
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    with logs_dir.joinpath("ctl_events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def build_ctl_writer() -> Callable[[dict[str, Any]], None]:
    if not CTL_ENDPOINT:
        return append_ctl_event_fallback

    def _send(event: dict[str, Any]) -> None:
        import requests

        response = requests.post(
            urljoin(CTL_ENDPOINT if CTL_ENDPOINT.endswith("/") else CTL_ENDPOINT + "/", "events"),
            json=event,
            timeout=5,
        )
        response.raise_for_status()

    return _send


def maybe_send_telegram(summary: dict[str, Any]) -> None:
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return
    import requests

    text = (
        f"commit_reflection {summary.get('status')}\n"
        f"commit: {summary.get('commit_hash')}\n"
        f"impact: {summary.get('metrics', {}).get('impact')}\n"
        f"payout: {summary.get('payout')} CT"
    )
    response = requests.post(
        f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
        json={"chat_id": TG_CHAT_ID, "text": text},
        timeout=5,
    )
    response.raise_for_status()


def _to_payload(commit: CommitInfo, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "hash": commit.hash,
        "message": commit.message,
        "files_changed": commit.files_changed,
        "insertions": commit.insertions,
        "deletions": commit.deletions,
        "files": commit.files,
        "metrics": metrics,
    }


def process_commit(commit: CommitInfo) -> dict[str, Any]:
    if is_merge(commit.message):
        return {"status": "skipped_merge", "commit_hash": commit.hash, "message": commit.message}

    metrics = heuristics_score(commit.files_changed, commit.insertions, commit.deletions)
    metrics["accuracy"] = compute_accuracy(commit.message)

    tx = CognitiveTransaction.create(actor=AGENT_ID, action="code_commit", payload=_to_payload(commit, metrics))

    cfl = CreationFeedbackLayer()
    ingest_result = cfl.ingest_transaction(tx)
    creation_score_delta = float(ingest_result.get("creation_score_delta", 0.0)) if isinstance(ingest_result, dict) else 0.0
    creation_score = float(getattr(cfl, "creation_score", creation_score_delta))

    payout_amount = Decimal("0")
    payout_receipt: dict[str, Any] | None = None
    if float(metrics["impact"]) > PAYOUT_THRESHOLD_IMPACT:
        if CELWalletAPI is None or TransferRequest is None:
            raise RuntimeError("CEL wallet dependencies are unavailable")
        wallet = CELWalletAPI(append_ctl_event=build_ctl_writer())
        wallet.create_wallet(PROJECT_TREASURY, PROJECT_TREASURY_BALANCE_CT)
        wallet.create_wallet(AGENT_ID, Decimal("0"))
        payout_amount = (MICRO_PAYOUT_CT * Decimal(str(metrics["impact"]))).quantize(Decimal("0.0001"))
        receipt = wallet.transfer(
            TransferRequest(
                trace_id=f"trace_commit_{commit.hash[:12]}",
                proposal_id=f"commit:{commit.hash[:8]}",
                from_agent_id=PROJECT_TREASURY,
                to_agent_id=AGENT_ID,
                amount_ct=payout_amount,
            )
        )
        payout_receipt = {
            "tx_ref": receipt.tx_ref,
            "from_balance_ct": str(receipt.from_balance_ct),
            "to_balance_ct": str(receipt.to_balance_ct),
        }

    status = "success" if payout_amount > 0 else "low_impact"
    out = {
        "status": status,
        "commit_hash": commit.hash,
        "message": commit.message,
        "metrics": metrics,
        "payout": str(payout_amount),
        "creation_score": creation_score,
        "creation_score_delta": creation_score_delta,
    }
    if payout_receipt:
        out["payout_receipt"] = payout_receipt
    return out


def main() -> int:
    try:
        summary = process_commit(last_commit())
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        maybe_send_telegram(summary)
        return 0
    except Exception as exc:
        LOG.exception("commit reflection failed")
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
