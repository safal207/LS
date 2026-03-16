from __future__ import annotations

from decimal import Decimal
import types

import tools.git_hooks.commit_reflection as cr


class DummyReceipt:
    def __init__(self, amount_ct: Decimal):
        self.amount_ct = amount_ct
        self.tx_ref = "tx_dummy_123"


class DummyWallet:
    def __init__(self, append_ctl_event=None):
        self.append_ctl_event = append_ctl_event

    def transfer(self, req):
        assert req.from_agent_id == cr.PROJECT_TREASURY
        return DummyReceipt(req.amount_ct)


def fake_run_git_merge(cmd: list[str]) -> str:
    if cmd[:2] == ["rev-parse", "HEAD"]:
        return "deadbeef\n"
    if cmd[:2] == ["show", "-s"]:
        return "Merge branch 'feature'\n"
    if cmd[:2] == ["show", "--numstat"]:
        return ""
    raise RuntimeError("unexpected")


def fake_run_git_small_change(cmd: list[str]) -> str:
    if cmd[:2] == ["rev-parse", "HEAD"]:
        return "aaaabbbb\n"
    if cmd[:2] == ["show", "-s"]:
        return "Fix bug in parser\n\nMore details\n"
    if cmd[:2] == ["show", "--numstat"]:
        return "10\t2\tfoo.py\n1\t0\tREADME.md\n"
    raise RuntimeError("unexpected")


def test_ignore_merge_commit(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cr, "_run_git", lambda cmd, cwd=None: fake_run_git_merge(cmd))

    rc = cr.main([])
    captured = capsys.readouterr()

    assert rc == 0
    assert "skipped_merge" in captured.out


def test_compute_metrics_and_transaction(monkeypatch) -> None:
    monkeypatch.setattr(cr, "_run_git", lambda cmd, cwd=None: fake_run_git_small_change(cmd))
    monkeypatch.setattr(cr, "_load_cel_types", lambda: (None, None))

    rc = cr.main([])

    assert rc == 0


def test_payout_called_when_impact_high(monkeypatch) -> None:
    monkeypatch.setattr(cr, "_run_git", lambda cmd, cwd=None: fake_run_git_small_change(cmd))
    monkeypatch.setattr(cr, "_load_cel_types", lambda: (lambda append_ctl_event=None: DummyWallet(append_ctl_event), lambda **kwargs: types.SimpleNamespace(**kwargs)))
    monkeypatch.setattr(cr, "PAYOUT_THRESHOLD_IMPACT", 0.0)

    rc = cr.main([])

    assert rc == 0
