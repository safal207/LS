import unittest
from _support import load_bundle, runtime


class MatchingTests(unittest.TestCase):
    def test_latest_preceding_event_is_selected(self):
        bundle = load_bundle()
        bundle["webEvents"].append(
            {
                "eventId": "wev_003",
                "eventName": "visit_intent_created",
                "occurredAt": "2026-07-04T10:30:00+03:00",
                "campaignToken": "rv_aaaaaaaaaaaaaaaaaaaa",
            }
        )
        result = runtime.calculate_attribution(bundle)
        self.assertEqual(result["matchedOrders"][0]["eventId"], "wev_003")
        self.assertEqual(result["matchedOrders"][0]["lagSeconds"], 1800)

    def test_equal_latest_events_are_ambiguous(self):
        bundle = load_bundle()
        bundle["webEvents"].append(
            {
                "eventId": "wev_004",
                "eventName": "visit_intent_created",
                "occurredAt": "2026-07-04T09:00:00+03:00",
                "campaignToken": "rv_aaaaaaaaaaaaaaaaaaaa",
            }
        )
        result = runtime.calculate_attribution(bundle)
        self.assertEqual(result["status"], "AMBIGUOUS")
        self.assertEqual(result["ambiguousOrderRefs"], ["ord_001"])
        self.assertEqual(result["totals"]["attributableOrders"], 0)

    def test_future_event_does_not_match(self):
        bundle = load_bundle()
        bundle["webEvents"][0]["occurredAt"] = "2026-07-04T12:00:00+03:00"
        result = runtime.calculate_attribution(bundle)
        self.assertIn("ord_001", result["unmatchedOrderRefs"])
