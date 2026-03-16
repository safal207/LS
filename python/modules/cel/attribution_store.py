from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class StoredPayout:
    payout_id: int
    project_id: str
    window_days: int
    policy_version: str
    agent_id: str
    amount: Decimal
    status: str
    input_snapshot_hash: str
    output_payout_hash: str
    dispute_reason: str | None
    dispute_approver: str | None


class AttributionStore:
    """SQLite-backed persistence for IARE events and payouts."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists creation_events (
                    event_id text primary key,
                    project_id text not null,
                    event_type text not null,
                    ts integer not null,
                    policy_version text not null,
                    payload_json text not null
                );

                create table if not exists reward_payouts (
                    payout_id integer primary key autoincrement,
                    project_id text not null,
                    window_days integer not null,
                    policy_version text not null,
                    agent_id text not null,
                    amount text not null,
                    status text not null,
                    input_snapshot_hash text not null,
                    output_payout_hash text not null,
                    dispute_reason text,
                    dispute_approver text
                );
                """
            )

    def save_event_if_new(
        self,
        *,
        event_id: str,
        project_id: str,
        event_type: str,
        ts: int,
        policy_version: str,
        payload_json: str,
    ) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                """
                insert or ignore into creation_events(
                    event_id, project_id, event_type, ts, policy_version, payload_json
                ) values (?, ?, ?, ?, ?, ?)
                """,
                (event_id, project_id, event_type, ts, policy_version, payload_json),
            )
            return cur.rowcount == 1

    def create_payout(
        self,
        *,
        project_id: str,
        window_days: int,
        policy_version: str,
        agent_id: str,
        amount: Decimal,
        status: str,
        input_snapshot_hash: str,
        output_payout_hash: str,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                insert into reward_payouts(
                    project_id, window_days, policy_version, agent_id, amount, status,
                    input_snapshot_hash, output_payout_hash
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    window_days,
                    policy_version,
                    agent_id,
                    str(amount),
                    status,
                    input_snapshot_hash,
                    output_payout_hash,
                ),
            )
            return int(cur.lastrowid)

    def get_payout(self, payout_id: int) -> StoredPayout | None:
        with self._connect() as conn:
            row = conn.execute("select * from reward_payouts where payout_id = ?", (payout_id,)).fetchone()
            if row is None:
                return None
            return self._row_to_payout(row)

    def update_payout_status(
        self,
        payout_id: int,
        *,
        status: str,
        dispute_reason: str | None = None,
        dispute_approver: str | None = None,
    ) -> StoredPayout | None:
        with self._connect() as conn:
            conn.execute(
                """
                update reward_payouts
                set status = ?,
                    dispute_reason = coalesce(?, dispute_reason),
                    dispute_approver = coalesce(?, dispute_approver)
                where payout_id = ?
                """,
                (status, dispute_reason, dispute_approver, payout_id),
            )
            row = conn.execute("select * from reward_payouts where payout_id = ?", (payout_id,)).fetchone()
            if row is None:
                return None
            return self._row_to_payout(row)

    def list_payouts(self, project_id: str) -> list[StoredPayout]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from reward_payouts where project_id = ? order by payout_id", (project_id,)
            ).fetchall()
            return [self._row_to_payout(row) for row in rows]

    @staticmethod
    def _row_to_payout(row: sqlite3.Row) -> StoredPayout:
        return StoredPayout(
            payout_id=int(row["payout_id"]),
            project_id=row["project_id"],
            window_days=int(row["window_days"]),
            policy_version=row["policy_version"],
            agent_id=row["agent_id"],
            amount=Decimal(row["amount"]),
            status=row["status"],
            input_snapshot_hash=row["input_snapshot_hash"],
            output_payout_hash=row["output_payout_hash"],
            dispute_reason=row["dispute_reason"],
            dispute_approver=row["dispute_approver"],
        )
