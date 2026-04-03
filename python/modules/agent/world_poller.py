# -*- coding: utf-8 -*-
"""WorldPoller — ingests external events into TemporalGraph as world-awareness nodes.

Sources polled on every tick (default 60s):
  - git log  : recent commits → "world:git:{short_hash}"
  - error log: Python ERROR/CRITICAL lines → "world:error:{slug}"
  - custom   : any callable returning list[WorldEvent]

Each event becomes a TemporalNode with resonance proportional to its
severity/importance. The system learns from the external world alongside
learning from the user and itself.

Node id schema
--------------
  world:git:{hash7}          resonance 0.55  harmony 0.10
  world:error:{slug12}       resonance 0.75  harmony 0.20
  world:critical:{slug12}    resonance 0.90  harmony 0.25
  world:custom:{slug12}      resonance from event
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from hexagon_core.temporal_graph import TemporalGraph

logger = logging.getLogger(__name__)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class WorldEvent:
    """A single external event to ingest."""
    source: str                        # "git", "error", "custom", …
    summary: str                       # human-readable, used for node id
    resonance: float = 0.55            # importance (0–1)
    harmony_bonus: float = 0.10
    raw: dict[str, Any] = field(default_factory=dict)


# ─── source collectors ────────────────────────────────────────────────────────

def _collect_git(repo_path: str, since_hash: Optional[str]) -> list[WorldEvent]:
    """Return WorldEvents for git commits newer than since_hash."""
    events: list[WorldEvent] = []
    try:
        cmd = ["git", "-C", repo_path, "log", "--oneline", "--no-color", "-20"]
        if since_hash:
            cmd.append(f"{since_hash}..HEAD")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return events
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(" ", 1)
            short_hash = parts[0][:7]
            message = parts[1] if len(parts) > 1 else "commit"
            # Infer resonance from commit prefix
            resonance = 0.55
            if any(kw in message.lower() for kw in ("fix", "bug", "error", "hotfix", "critical")):
                resonance = 0.75
            elif any(kw in message.lower() for kw in ("feat", "add", "new", "implement")):
                resonance = 0.65
            elif any(kw in message.lower() for kw in ("refactor", "perf", "optim")):
                resonance = 0.60
            events.append(WorldEvent(
                source="git",
                summary=f"{short_hash}: {message[:60]}",
                resonance=resonance,
                harmony_bonus=0.10,
                raw={"hash": short_hash, "message": message},
            ))
    except Exception as exc:
        logger.debug("WorldPoller git collect error: %s", exc)
    return events


def _collect_errors(log_path: str, last_pos: int) -> tuple[list[WorldEvent], int]:
    """Tail a log file for ERROR/CRITICAL lines since last_pos. Returns (events, new_pos)."""
    events: list[WorldEvent] = []
    try:
        if not os.path.exists(log_path):
            return events, last_pos
        size = os.path.getsize(log_path)
        if size <= last_pos:
            return events, last_pos
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(last_pos)
            new_lines = f.read()
            new_pos = f.tell()
        for line in new_lines.splitlines():
            clean = _ANSI_RE.sub("", line)
            is_critical = "CRITICAL" in clean or "FATAL" in clean
            is_error = "ERROR" in clean
            if not (is_critical or is_error):
                continue
            resonance = 0.90 if is_critical else 0.75
            events.append(WorldEvent(
                source="critical" if is_critical else "error",
                summary=clean[clean.find("ERROR"):clean.find("ERROR") + 80].strip() or clean[:80],
                resonance=resonance,
                harmony_bonus=0.25 if is_critical else 0.20,
                raw={"line": clean[:200]},
            ))
        return events, new_pos
    except Exception as exc:
        logger.debug("WorldPoller error log collect: %s", exc)
        return events, last_pos


# ─── main class ───────────────────────────────────────────────────────────────

class WorldPoller:
    """Polls external sources and ingests events as TemporalGraph world-nodes.

    Args:
        temporal:       TemporalGraph (or TemporalContext) to write into.
        repo_path:      Path to git repository to watch. None = disabled.
        log_path:       Path to application log file to tail. None = disabled.
        interval_s:     Polling interval in seconds (default 60).
        extra_sources:  List of callables () → list[WorldEvent] for custom feeds.
    """

    def __init__(
        self,
        temporal: "TemporalGraph",
        repo_path: Optional[str] = None,
        log_path: Optional[str] = None,
        interval_s: float = 60.0,
        extra_sources: Optional[List[Callable[[], List[WorldEvent]]]] = None,
    ) -> None:
        self._temporal = temporal
        self._repo_path = repo_path or os.getcwd()
        self._log_path = log_path
        self._interval_s = interval_s
        self._extra_sources: List[Callable[[], List[WorldEvent]]] = extra_sources or []

        # State between ticks
        self._last_git_hash: Optional[str] = None
        self._last_log_pos: int = 0
        self._ingested: set[str] = set()   # node ids already in graph

    # ── public ────────────────────────────────────────────────────────────────

    def tick(self) -> int:
        """Run one poll cycle. Returns number of new nodes ingested."""
        events: list[WorldEvent] = []

        # Git
        git_events = _collect_git(self._repo_path, self._last_git_hash)
        if git_events:
            # Update cursor to most recent hash
            self._last_git_hash = git_events[0].raw.get("hash")
        events.extend(git_events)

        # Error log
        if self._log_path:
            err_events, self._last_log_pos = _collect_errors(self._log_path, self._last_log_pos)
            events.extend(err_events)

        # Custom sources
        for source_fn in self._extra_sources:
            try:
                events.extend(source_fn())
            except Exception as exc:
                logger.debug("WorldPoller custom source error: %s", exc)

        count = 0
        for event in events:
            count += self._ingest(event)
        if count:
            logger.info("WorldPoller: ingested %d new world events", count)
        return count

    def stats(self) -> dict[str, Any]:
        world_nodes = [
            (nid, n.resonance, n.velocity)
            for nid, n in self._temporal.nodes.items()
            if nid.startswith("world:")
        ]
        return {
            "world_nodes": len(world_nodes),
            "top": sorted(world_nodes, key=lambda x: x[1], reverse=True)[:5],
        }

    # ── internal ──────────────────────────────────────────────────────────────

    def _ingest(self, event: WorldEvent) -> int:
        """Ingest one WorldEvent. Returns 1 if new node created/strengthened, 0 if skipped."""
        from hexagon_core.temporal_graph import TemporalNode

        slug = hashlib.md5(event.summary.encode()).hexdigest()[:12]
        node_id = f"world:{event.source}:{slug}"

        with self._temporal._graph_lock:
            existing = self._temporal.nodes.get(node_id)
            if existing is not None:
                if node_id in self._ingested:
                    return 0   # already processed this tick
                # Seen before but not this tick — strengthen slightly
                existing.update_resonance(min(1.0, existing.resonance + 0.05))
                self._ingested.add(node_id)
                return 1
            node = TemporalNode(
                id=node_id,
                resonance=event.resonance,
                harmony_bonus=event.harmony_bonus,
            )
            self._temporal.nodes[node_id] = node

        self._temporal.align_to_axis(node)
        self._ingested.add(node_id)
        logger.debug(
            "WorldPoller → temporal: %s resonance=%.3f source=%s",
            node_id, node.resonance, event.source,
        )
        return 1
