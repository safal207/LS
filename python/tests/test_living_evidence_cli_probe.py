from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from multi_model_review.evidence_probes import probe_cli_documentation_parity  # noqa: E402


class LivingEvidenceCliProbeTests(unittest.TestCase):
    def test_required_flag_survives_nested_default_call(self) -> None:
        argparse_source = """
parser.add_argument(
    "--schema",
    default=resolve_default(1, nested(2)),
    required=True,
)
parser.add_argument("--optional", default=None)
"""
        finding = probe_cli_documentation_parity(
            argparse_source=argparse_source,
            validator_path="validate.py",
            markdown="""```bash
python validate.py
```""",
            spec_path="spec.md",
            known_paths=[],
        )
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.counterexample_recipe["required_flags"], ["--schema"])
        self.assertEqual(finding.counterexample_recipe["missing_flags"], ["--schema"])

        documented = probe_cli_documentation_parity(
            argparse_source=argparse_source,
            validator_path="validate.py",
            markdown="""```bash
python validate.py --schema schema.json
```""",
            spec_path="spec.md",
            known_paths=["schema.json"],
        )
        self.assertIsNone(documented)


if __name__ == "__main__":
    unittest.main()
