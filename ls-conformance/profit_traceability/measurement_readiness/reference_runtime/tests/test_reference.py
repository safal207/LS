import unittest
from _support import load_bundle, runtime


class ReferenceTests(unittest.TestCase):
    def test_reference_totals_and_classification(self):
        result = runtime.calculate_attribution(load_bundle())
        self.assertEqual(result["status"], "ATTRIBUTION_CALCULATED")
        self.assertEqual(result["totals"]["attributableOrders"], 1)
        self.assertEqual(result["totals"]["attributableGrossRevenue"], "300.00")
        self.assertEqual(result["totals"]["attributableVariableCosts"], "140.00")
        self.assertEqual(
            result["totals"]["grossContributionBeforeAcquisitionAndExperimentCosts"],
            "160.00",
        )
        self.assertEqual(result["expiredOrderRefs"], ["ord_002"])
        self.assertEqual(result["unmatchedOrderRefs"], ["ord_003"])

    def test_result_never_claims_profit_readiness(self):
        result = runtime.calculate_attribution(load_bundle())
        self.assertFalse(result["profitDecision"]["ready"])
        self.assertNotIn("netProfit", result["totals"])
