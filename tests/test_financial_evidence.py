"""Synthetic regression cases; no provider SDK or credentials."""
import json
import socket
import unittest
from unittest.mock import patch

from src.financial_evidence import monthly_evidence, provider_savings, validated_cost_rows, savings_evidence_summary
from src.recommendations.engine import RecommendationEngine
from src.tools.handlers import ToolHandlers


def rec(id_, amount, currency, resource=None):
    return {
        "id": id_, "problem": "Reserved instance", "solution": "Review reserved instance",
        "estimated_monthly_savings": amount, "savings_currency": currency,
        "resource_metadata": {"resource_id": resource},
    }


class FinancialEvidenceTests(unittest.TestCase):
    def test_missing_invalid_or_negative_estimates_are_unknown(self):
        for amount, currency in [(30, None), (True, "USD"), ("NaN", "EUR"), (float("inf"), "EUR"), (-1, "EUR"), ("bad", "EUR"), (3, "??")]:
            with self.subTest(amount=amount, currency=currency):
                self.assertEqual(monthly_evidence(amount, currency), (None, None))
        self.assertEqual(monthly_evidence(0, "eur"), (0.0, "EUR"))

    def test_provider_period_is_not_invented(self):
        value = provider_savings("120", "usd")
        self.assertEqual((value["amount"], value["currency"], value["period"]), (120.0, "USD", "unknown"))

    def test_mixed_currency_actual_cost_rejected(self):
        with self.assertRaises(ValueError):
            validated_cost_rows([{"Cost": 10, "Currency": "EUR"}, {"Cost": 20, "Currency": "USD"}])
        with self.assertRaises(ValueError):
            validated_cost_rows([{"Cost": 10}])
        with self.assertRaises(ValueError):
            validated_cost_rows([{"Cost": "invalid", "Currency": "EUR"}])

    def test_actual_cost_preserves_credits_and_empty_is_unknown(self):
        total, currency, _ = validated_cost_rows([{"Cost": "10.20", "Currency": "eur"}, {"Cost": "-0.10", "Currency": "EUR"}])
        self.assertEqual(str(total), "10.10")
        self.assertEqual(currency, "EUR")
        self.assertEqual(validated_cost_rows([]), (None, None, []))

    def test_only_reporting_currency_ranked_no_total(self):
        rows = RecommendationEngine().correlate({"currency": "EUR"}, {}, {"recommendations": [
            rec("eur", 25, "EUR", "same"), rec("usd", 900, "USD", "same"), rec("unknown", None, None),
        ]})
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["id"], "eur")
        self.assertTrue(rows[0]["is_quick_win"])
        for row in rows[1:]:
            self.assertIsNone(row["priority_score"])
            self.assertFalse(row["is_quick_win"])
        self.assertTrue(all(r["advisory_only"] and r["requires_human_review"] for r in rows))
        evidence = savings_evidence_summary(rows)
        self.assertEqual(evidence["known_monthly_estimate_count_by_currency"], {"EUR": 1, "USD": 1})
        self.assertEqual(evidence["unknown_monthly_estimate_count"], 1)
        self.assertIsNone(evidence["aggregate_monthly_savings"])

    def test_no_reporting_currency_no_rank(self):
        row = RecommendationEngine().correlate({}, {}, {"recommendations": [rec("a", 25, "EUR")]})[0]
        self.assertIsNone(row["priority_score"])
        self.assertFalse(row["is_quick_win"])

    def test_idle_resources_have_no_price_assumption(self):
        rows = RecommendationEngine().correlate({"currency": "USD"}, {}, {}, {
            "unused_disks": {"unused_disks": [{"id": "disk-1", "name": "disk", "sizeGb": 100}]},
            "unused_pips": {"unattached_public_ips": [{"id": "ip-1", "name": "ip"}]},
        })
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertIsNone(row["estimated_monthly_savings"])
            self.assertIsNone(row["savings_currency"])
            self.assertEqual(row["risk"], "high")
            self.assertFalse(row["is_quick_win"])

    def test_spend_observation_checks_scope_dates_and_currency(self):
        scope = {"scope": "subscriptions/demo", "from_date": "2026-01-01", "to_date": "2026-01-31"}
        summary = dict(scope, total_cost=100, currency="EUR")
        drivers = dict(scope, currency="EUR", top_drivers=[{"name": "Compute", "cost": 40, "percentage": 99}])
        rows = RecommendationEngine().correlate(summary, drivers, {})
        self.assertEqual(len(rows), 1)
        self.assertIn("40.0%", rows[0]["title"])
        self.assertIsNone(rows[0]["estimated_monthly_savings"])
        self.assertEqual(RecommendationEngine().correlate(summary, dict(drivers, currency="USD"), {}), [])
        self.assertEqual(RecommendationEngine().correlate(summary, dict(drivers, scope="other"), {}), [])


class FakeCost:
    def __init__(self): self.calls = []
    def get_cost_summary(self, **kwargs):
        self.calls.append(kwargs)
        return {"currency": "EUR", "total_cost": 100}
    def get_top_cost_drivers(self, **kwargs):
        self.calls.append(kwargs)
        return {"currency": "EUR", "top_drivers": []}


class FakeAdvisor:
    def __init__(self): self.calls = []
    def get_cost_recommendations(self, **kwargs):
        self.calls.append(kwargs)
        return {"recommendations": [rec("synthetic", 25, "EUR")]}


class FakeGraph:
    def __init__(self): self.calls = []
    def get_idle_vms(self):
        self.calls.append("vm")
        return {"count": 0, "idle_vms": []}
    def get_unused_disks(self):
        self.calls.append("disk")
        return {"count": 0, "unused_disks": []}
    def get_unattached_public_ips(self):
        self.calls.append("ip")
        return {"count": 0, "unattached_public_ips": []}


class OfflineToolTests(unittest.TestCase):
    def setUp(self):
        self.cost, self.advisor, self.graph = FakeCost(), FakeAdvisor(), FakeGraph()
        self.handlers = ToolHandlers(cost=self.cost, advisor=self.advisor, graph=self.graph, subscription_id="demo")
        guard = patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden"))
        guard.start()
        self.addCleanup(guard.stop)

    def test_other_subscription_rejected_before_provider_calls(self):
        for tool in ("get_cost_summary", "correlate_cost_and_advisor", "get_idle_resources"):
            result = json.loads(self.handlers.dispatch(tool, {"subscription_id": "other"}))
            self.assertIn("error", result)
        self.assertEqual((self.cost.calls, self.advisor.calls, self.graph.calls), ([], [], []))

    def test_resource_group_omits_subscription_idle_scan(self):
        result = json.loads(self.handlers.dispatch("correlate_cost_and_advisor", {"resource_group": "demo-rg"}))
        self.assertNotIn("error", result)
        self.assertFalse(result["idle_scan_included"])
        self.assertEqual(self.graph.calls, [])
        self.assertEqual(self.advisor.calls, [{"resource_group": "demo-rg"}])
        self.assertIsNone(result["savings_evidence_summary"]["aggregate_monthly_savings"])

    def test_subscription_correlation_offline(self):
        result = json.loads(self.handlers.dispatch("correlate_cost_and_advisor", {"subscription_id": "DEMO"}))
        self.assertNotIn("error", result)
        self.assertTrue(result["idle_scan_included"])
        self.assertEqual(self.graph.calls, ["vm", "disk", "ip"])
        self.assertEqual(len(result["quick_wins"]), 1)
        self.assertNotIn("total_potential_monthly_savings", result)


if __name__ == "__main__":
    unittest.main()
