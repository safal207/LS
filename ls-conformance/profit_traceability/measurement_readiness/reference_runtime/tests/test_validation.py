import unittest
from _support import load_bundle, runtime


class ValidationTests(unittest.TestCase):
    def test_non_object_input_is_rejected(self):
        with self.assertRaisesRegex(runtime.AttributionError, "JSON object"):
            runtime.calculate_attribution([])

    def test_experiment_mode_is_rejected(self):
        bundle = load_bundle()
        bundle["mode"] = "EXPERIMENT"
        with self.assertRaisesRegex(runtime.AttributionError, "only authorizes BASELINE"):
            runtime.calculate_attribution(bundle)

    def test_measurement_plan_mismatch_is_rejected(self):
        bundle = load_bundle()
        bundle["measurementPlanRef"] = "MPLAN-OTHER-001"
        with self.assertRaisesRegex(runtime.AttributionError, "approved readiness plan"):
            runtime.calculate_attribution(bundle)

    def test_attribution_window_mismatch_is_rejected(self):
        bundle = load_bundle()
        bundle["attributionWindowHours"] = 48
        with self.assertRaisesRegex(runtime.AttributionError, "approved 24-hour"):
            runtime.calculate_attribution(bundle)

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

    def test_unsafe_event_and_order_ids_are_rejected(self):
        for field, collection, value in (
            ("eventId", "webEvents", "wev_bad@id"),
            ("orderId", "posOrders", "ord_bad@id"),
        ):
            with self.subTest(field=field):
                bundle = load_bundle()
                bundle[collection][0][field] = value
                with self.assertRaisesRegex(runtime.AttributionError, "Id is invalid"):
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

    def test_money_rejects_noncanonical_notation(self):
        for value in ("300.000", "3E+2", "+300.00", "0300.00"):
            with self.subTest(value=value):
                bundle = load_bundle()
                bundle["posOrders"][0]["grossRevenue"] = value
                with self.assertRaisesRegex(runtime.AttributionError, "canonical"):
                    runtime.calculate_attribution(bundle)

    def test_unknown_top_level_field_is_rejected(self):
        bundle = load_bundle()
        bundle["unexpectedField"] = "sensitive-value"
        with self.assertRaisesRegex(
            runtime.AttributionError, "unknown top-level fields"
        ):
            runtime.calculate_attribution(bundle)
