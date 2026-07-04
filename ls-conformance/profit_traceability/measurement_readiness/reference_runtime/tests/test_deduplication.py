import copy
import unittest
from _support import load_bundle, runtime


class DeduplicationTests(unittest.TestCase):
    def test_identical_duplicates_are_deduplicated(self):
        bundle = load_bundle()
        bundle["posOrders"].append(copy.deepcopy(bundle["posOrders"][0]))
        result = runtime.calculate_attribution(bundle)
        self.assertEqual(result["deduplication"]["inputPosOrders"], 4)
        self.assertEqual(result["deduplication"]["uniquePosOrders"], 3)

    def test_conflicting_duplicate_event_fails_closed(self):
        bundle = load_bundle()
        conflicting = copy.deepcopy(bundle["webEvents"][0])
        conflicting["campaignToken"] = "rv_dddddddddddddddddddd"
        bundle["webEvents"].append(conflicting)
        with self.assertRaisesRegex(
            runtime.AttributionError, "conflicting duplicate web event"
        ):
            runtime.calculate_attribution(bundle)

    def test_conflicting_duplicate_order_fails_closed(self):
        bundle = load_bundle()
        conflicting = copy.deepcopy(bundle["posOrders"][0])
        conflicting["grossRevenue"] = "301.00"
        bundle["posOrders"].append(conflicting)
        with self.assertRaisesRegex(
            runtime.AttributionError, "conflicting duplicate POS order"
        ):
            runtime.calculate_attribution(bundle)
