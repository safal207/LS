import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "validate.py"
spec = importlib.util.spec_from_file_location("profit_trace_validator", MODULE_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)

FIXTURE = ROOT / "fixtures" / "robys_menu_to_visit.blocked.json"


class ProfitProductBindingTests(unittest.TestCase):
    def test_candidate_must_reference_bundle_product(self):
        bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))
        changed = copy.deepcopy(bundle)
        changed["product"]["productId"] = "PROD-OTHER-WEB"

        with self.assertRaisesRegex(
            validator.ProfitTraceValidationError,
            "sourceProductRefs must include product.productId",
        ):
            validator.validate_semantics(changed)


if __name__ == "__main__":
    unittest.main()
