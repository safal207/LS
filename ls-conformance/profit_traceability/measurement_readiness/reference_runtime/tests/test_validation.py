import unittest
from _support import load_bundle, runtime


class ValidationTests(unittest.TestCase):
    def test_currency_mismatch_is_rejected(self):
        bundle = load_bundle()
        bundle["posOrders"][0]["currency"] = "USD"
        with self.assertRaisesRegex(runtime.AttributionError, "currency must match"):
            runtime.calculate_attribution(bundle)

    def test_invalid_token_is_rejected(self):
        bundle = load_bundle()
        bundle["webEvents"][0]["campaignToken"] = "not-a-valid-token"
        with self.assertRaisesRegex(
            runtime.AttributionError, "campaignToken is invalid"
        ):
            runtime.calculate_attribution(bundle)

    def test_money_requires_decimal_string(self):
        bundle = load_bundle()
        bundle["posOrders"][0]["grossRevenue"] = 300.0
        with self.assertRaisesRegex(runtime.AttributionError, "decimal string"):
            runtime.calculate_attribution(bundle)

    def test_money_rejects_excess_precision(self):
        bundle = load_bundle()
        bundle["posOrders"][0]["grossRevenue"] = "300.001"
        with self.assertRaisesRegex(
            runtime.AttributionError, "at most 2 decimal places"
        ):
            runtime.calculate_attribution(bundle)

    def test_unknown_top_level_field_is_rejected(self):
        bundle = load_bundle()
        bundle["unexpectedField"] = "sensitive-value"
        with self.assertRaisesRegex(
            runtime.AttributionError, "unknown top-level fields"
        ):
            runtime.calculate_attribution(bundle)
