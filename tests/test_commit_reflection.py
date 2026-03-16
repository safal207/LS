from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import tools.git_hooks.commit_reflection as cr


@dataclass
class DummyTx:
    payload: dict


class DummyCognitiveTransaction:
    @staticmethod
    def create(actor: str, action: str, payload: dict):
        assert actor
        assert action == "code_commit"
        return DummyTx(payload=payload)


class DummyCreationFeedbackLayer:
    def __init__(self) -> None:
        self.creation_score = 0.0
        self.ingested: list[DummyTx] = []

    def ingest_transaction(self, tx: DummyTx) -> dict[str, float]:
        self.ingested.append(tx)
        self.creation_score += 0.42
        return {"creation_score_delta": 0.42}




class DummyTransferRequest:
    def __init__(self, trace_id: str, proposal_id: str, from_agent_id: str, to_agent_id: str, amount_ct: Decimal):
        self.trace_id = trace_id
        self.proposal_id = proposal_id
        self.from_agent_id = from_agent_id
        self.to_agent_id = to_agent_id
        self.amount_ct = amount_ct

class DummyWallet:
    transferred = False

    def __init__(self, append_ctl_event=None):
        self.append_ctl_event = append_ctl_event

    def create_wallet(self, agent_id: str, initial_balance_ct: Decimal) -> None:
        return None

    def transfer(self, req):
        DummyWallet.transferred = True
        if self.append_ctl_event:
            self.append_ctl_event({"trace_id": req.trace_id, "proposal_id": req.proposal_id})

        class Receipt:
            tx_ref = "tx1"
            from_balance_ct = Decimal("1.0")
            to_balance_ct = Decimal("2.0")

        return Receipt()


def test_ignore_merge_commit() -> None:
    commit = cr.CommitInfo(
        hash="abc123",
        message="Merge branch 'feature/x'",
        files_changed=1,
        insertions=10,
        deletions=2,
        files=["a.py"],
    )
    summary = cr.process_commit(commit)
    assert summary["status"] == "skipped_merge"


def test_compute_metrics_and_transaction(monkeypatch) -> None:
    monkeypatch.setattr(cr, "CognitiveTransaction", DummyCognitiveTransaction)
    monkeypatch.setattr(cr, "CreationFeedbackLayer", DummyCreationFeedbackLayer)
    monkeypatch.setattr(cr, "PAYOUT_THRESHOLD_IMPACT", 0.99)

    commit = cr.CommitInfo(
        hash="abc1234",
        message="fix test flow",
        files_changed=2,
        insertions=20,
        deletions=0,
        files=["a.py", "b.py"],
    )
    summary = cr.process_commit(commit)
    assert summary["status"] == "low_impact"
    assert summary["metrics"]["impact"] > 0
    assert summary["metrics"]["accuracy"] >= 0.85


def test_payout_called_when_impact_high(monkeypatch, tmp_path) -> None:
    DummyWallet.transferred = False
    monkeypatch.setattr(cr, "CognitiveTransaction", DummyCognitiveTransaction)
    monkeypatch.setattr(cr, "CreationFeedbackLayer", DummyCreationFeedbackLayer)
    monkeypatch.setattr(cr, "CELWalletAPI", DummyWallet)
    monkeypatch.setattr(cr, "TransferRequest", DummyTransferRequest)
    monkeypatch.setattr(cr, "PAYOUT_THRESHOLD_IMPACT", 0.1)
    monkeypatch.chdir(tmp_path)

    commit = cr.CommitInfo(
        hash="abcdef012345",
        message="refactor: large update",
        files_changed=7,
        insertions=190,
        deletions=40,
        files=["x.py"],
    )
    summary = cr.process_commit(commit)
    assert summary["status"] == "success"
    assert DummyWallet.transferred is True
    assert Decimal(summary["payout"]) > 0
    ctl_log = tmp_path / "logs" / "ctl_events.jsonl"
    assert ctl_log.exists()
