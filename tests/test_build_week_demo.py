from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "scripts" / "run_build_week_demo.sh"


class BuildWeekDemoTests(unittest.TestCase):
    def test_one_command_demo_reproduces_all_four_scenarios(self) -> None:
        env = os.environ.copy()
        env["PYTHON"] = sys.executable

        result = subprocess.run(
            [str(DEMO)],
            cwd=ROOT.parent,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stderr)
        expected_rows = (
            ("Scenario 1: stale approval", "BLOCKED", "STALE_APPROVAL"),
            ("Scenario 2: spoofed reviewer", "BLOCKED", "UNTRUSTED_REVIEWER"),
            ("Scenario 3: required lane absent", "BLOCKED", "REQUIRED_LANE_NOT_RUN"),
            ("Scenario 4: current-head review", "TRUSTED", "ALL_REQUIRED_EVIDENCE_VALID"),
        )
        for prefix, verdict, reason_code in expected_rows:
            row = next(line for line in result.stdout.splitlines() if line.startswith(prefix))
            self.assertIn(verdict, row)
            self.assertTrue(row.endswith(reason_code), row)
        self.assertIn("Demo result: 4/4 scenarios matched", result.stdout)


if __name__ == "__main__":
    unittest.main()
