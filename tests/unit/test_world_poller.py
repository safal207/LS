# -*- coding: utf-8 -*-
"""Unit tests for WorldPoller — external event ingestion into TemporalGraph."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODULES = os.path.join(ROOT, "python", "modules")
for p in (ROOT, MODULES):
    if p not in sys.path:
        sys.path.insert(0, p)

from agent.world_poller import WorldPoller, WorldEvent, _collect_errors
from hexagon_core.temporal_graph import TemporalGraph, TemporalNode


class TestWorldPollerIngest(unittest.TestCase):
    def _make_poller(self, **kwargs) -> WorldPoller:
        tg = TemporalGraph()
        return WorldPoller(temporal=tg, repo_path=None, log_path=None, **kwargs), tg

    def test_ingest_creates_world_node(self):
        tg = TemporalGraph()
        poller = WorldPoller(temporal=tg, repo_path=None, log_path=None)
        event = WorldEvent(source="git", summary="abc1234: fix critical bug", resonance=0.75)
        poller._ingest(event)

        world_nodes = [k for k in tg.nodes if k.startswith("world:")]
        self.assertEqual(len(world_nodes), 1)
        node = tg.nodes[world_nodes[0]]
        self.assertAlmostEqual(node.resonance, 0.75, delta=0.15)  # align_to_axis may nudge it

    def test_ingest_deduplicates_same_event(self):
        tg = TemporalGraph()
        poller = WorldPoller(temporal=tg, repo_path=None, log_path=None)
        event = WorldEvent(source="error", summary="NullPointerException in loop", resonance=0.75)

        poller._ingest(event)
        poller._ingest(event)  # second time — same tick

        world_nodes = [k for k in tg.nodes if k.startswith("world:")]
        self.assertEqual(len(world_nodes), 1)  # not duplicated

    def test_error_node_has_higher_resonance_than_git_node(self):
        tg = TemporalGraph()
        poller = WorldPoller(temporal=tg, repo_path=None, log_path=None)

        poller._ingest(WorldEvent(source="git", summary="commit: update readme", resonance=0.55))
        poller._ingest(WorldEvent(source="critical", summary="CRITICAL system failure", resonance=0.90))

        nodes = {k: v for k, v in tg.nodes.items() if k.startswith("world:")}
        git_node = next(n for k, n in nodes.items() if "git" in k)
        crit_node = next(n for k, n in nodes.items() if "critical" in k)
        self.assertGreater(crit_node.resonance, git_node.resonance)

    def test_critical_error_can_become_axis(self):
        tg = TemporalGraph()
        poller = WorldPoller(temporal=tg, repo_path=None, log_path=None)

        # Put a mild subconscious node
        tg.nodes["subconscious:reactive"] = TemporalNode(
            id="subconscious:reactive", resonance=0.65, harmony_bonus=0.1
        )
        # Ingest a CRITICAL event
        poller._ingest(WorldEvent(source="critical", summary="CRITICAL db connection lost", resonance=0.90, harmony_bonus=0.25))

        axis = tg.get_meritocratic_axis()
        self.assertTrue(axis.id.startswith("world:critical"))

    def test_stats_returns_world_node_count(self):
        tg = TemporalGraph()
        poller = WorldPoller(temporal=tg, repo_path=None, log_path=None)

        for i in range(3):
            poller._ingest(WorldEvent(source="git", summary=f"commit{i}: change", resonance=0.55))

        stats = poller.stats()
        self.assertEqual(stats["world_nodes"], 3)

    def test_custom_source_is_called_on_tick(self):
        tg = TemporalGraph()
        fired = []

        def my_source():
            fired.append(1)
            return [WorldEvent(source="custom", summary="heartbeat event", resonance=0.50)]

        poller = WorldPoller(temporal=tg, repo_path=None, log_path=None, extra_sources=[my_source])
        poller.tick()

        self.assertEqual(len(fired), 1)
        world_nodes = [k for k in tg.nodes if k.startswith("world:custom")]
        self.assertEqual(len(world_nodes), 1)


class TestErrorLogCollect(unittest.TestCase):
    def test_collects_error_lines_from_log(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("INFO normal line\n")
            f.write("ERROR something went wrong in process\n")
            f.write("DEBUG debug line\n")
            f.write("CRITICAL database connection lost\n")
            fname = f.name

        try:
            events, pos = _collect_errors(fname, last_pos=0)
            self.assertEqual(len(events), 2)
            sources = {e.source for e in events}
            self.assertIn("error", sources)
            self.assertIn("critical", sources)
            # CRITICAL should have higher resonance
            crit = next(e for e in events if e.source == "critical")
            err = next(e for e in events if e.source == "error")
            self.assertGreater(crit.resonance, err.resonance)
            # pos should be at end of file
            self.assertEqual(pos, os.path.getsize(fname))
        finally:
            os.unlink(fname)

    def test_incremental_read_from_last_pos(self):
        """Second call with last_pos should only return new lines."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("ERROR first error\n")
            fname = f.name

        try:
            events1, pos1 = _collect_errors(fname, last_pos=0)
            self.assertEqual(len(events1), 1)

            # Append more content
            with open(fname, "a") as f2:
                f2.write("ERROR second error\n")

            events2, pos2 = _collect_errors(fname, last_pos=pos1)
            self.assertEqual(len(events2), 1)
            self.assertIn("second", events2[0].summary.lower() + events2[0].raw.get("line", "").lower())
        finally:
            os.unlink(fname)


if __name__ == "__main__":
    unittest.main()
