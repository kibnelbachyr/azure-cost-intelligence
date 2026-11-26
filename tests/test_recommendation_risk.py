"""Offline regression tests for deterministic recommendation heuristics."""
import unittest

from src.recommendations.engine import RecommendationEngine, _classify_risk


class RecommendationRiskTests(unittest.TestCase):
    def test_destructive_terms_override_lower_risk_terms(self):
        for text in ("Delete unused disk", "Remove unattached public IP", "Migrate idle VM"):
            with self.subTest(text=text):
                self.assertEqual(_classify_risk(text), "high")

    def test_moderate_terms_override_low_terms(self):
        self.assertEqual(_classify_risk("Resize idle VM"), "medium")
        self.assertEqual(_classify_risk("Review backup"), "low")
        self.assertEqual(_classify_risk("Review usage"), "medium")

    def test_destructive_advisor_recommendation_is_not_quick_win(self):
        recs = RecommendationEngine().correlate({}, {}, {"recommendations": [{
            "name": "example", "problem": "Unused disk",
            "solution": "Delete unused disk", "estimated_monthly_savings": 25,
        }]})
        self.assertEqual(recs[0]["risk"], "high")
        self.assertFalse(recs[0]["is_quick_win"])

    def test_generated_deletion_candidates_require_review(self):
        recs = RecommendationEngine().correlate({}, {}, {}, {
            "idle_vms": {"idle_vms": [{"name": "vm-demo", "id": "vm-1"}]},
            "unused_disks": {"unused_disks": [{"name": "disk-demo", "id": "disk-1", "sizeGb": 100}]},
            "unused_pips": {"unattached_public_ips": [{"name": "ip-demo", "id": "ip-1"}]},
        })
        self.assertEqual(len(recs), 3)
        for rec in recs:
            self.assertEqual(rec["risk"], "high")
            self.assertFalse(rec["is_quick_win"])
            self.assertTrue(rec["trade_offs"])

    def test_low_risk_positive_savings_remain_eligible(self):
        recs = RecommendationEngine().correlate({"currency": "EUR"}, {}, {"recommendations": [{
            "name": "example", "problem": "Reserved instance",
            "solution": "Review reserved instance", "estimated_monthly_savings": 25, "savings_currency": "EUR",
        }]})
        self.assertTrue(recs[0]["is_quick_win"])


if __name__ == "__main__":
    unittest.main()
