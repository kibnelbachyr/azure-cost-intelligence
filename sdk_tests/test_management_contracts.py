"""Real Azure management clients, synthetic HTTP responses, no Azure credentials."""
import json
import socket
import unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

from azure.core.credentials import AccessToken
from azure.core.pipeline.transport import RequestsTransport, RequestsTransportResponse
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.advisor import AdvisorManagementClient
from azure.mgmt.resourcegraph import ResourceGraphClient
from requests import Response

from src.services.cost_management import CostManagementService
from src.services.advisor import AdvisorService
from src.services.resource_graph import ResourceGraphService
from src.tools.handlers import ToolHandlers

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "provider-responses-v1.json").read_text())
SUB = FIXTURES["subscription_id"]
SETTINGS = SimpleNamespace(azure_subscription_id=SUB, default_cost_lookback_days=30, top_cost_drivers_limit=10)


class FictionalCredential:
    def get_token(self, *scopes, **kwargs):
        return AccessToken("fictional-test-token", 4102444800)


class FixtureResponse(RequestsTransportResponse):
    # New code-generated SDKs use response.json(); older ones use body/text.
    def json(self):
        return json.loads(self.body())


class FixtureTransport(RequestsTransport):
    def __init__(self, *responses):
        super().__init__()
        self.responses = deque(responses)
        self.calls = []

    def send(self, request, **kwargs):
        if not self.responses:
            raise AssertionError("Unexpected SDK HTTP request")
        expected_method, expected_path, body = self.responses.popleft()
        path = unquote(urlsplit(request.url).path).rstrip("/").lower()
        if request.method.upper() != expected_method or not path.endswith(expected_path.lower()):
            raise AssertionError(f"Unexpected request method/path: {request.method} {path}")
        raw = request.body
        payload = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) and raw else raw
        self.calls.append((request.method, path, payload, urlsplit(request.url).query))
        response = Response()
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        response._content = json.dumps(body).encode("utf-8")
        response.encoding = "utf-8"
        response.url = request.url
        return FixtureResponse(request, response)


class ManagementContracts(unittest.TestCase):
    def setUp(self):
        # Fixture transport cannot send real HTTP; extra guards catch direct socket paths.
        for target, attr in [(socket.socket, "connect"), (socket.socket, "connect_ex"), (socket, "getaddrinfo")]:
            guard = patch.object(target, attr, side_effect=AssertionError("Network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)

    def cost(self, fixture, scope=None):
        suffix = (scope or f"/subscriptions/{SUB}") + "/providers/Microsoft.CostManagement/query"
        transport = FixtureTransport(("POST", suffix, FIXTURES[fixture]))
        client = CostManagementClient(credential=FictionalCredential(), transport=transport, retry_total=0)
        self.addCleanup(client.close)
        service = CostManagementService(client=client, settings=SETTINGS)
        service._date_range = lambda days: ("2026-01-01", "2026-01-31")
        return service, transport

    def advisor(self):
        transport = FixtureTransport(("GET", f"/subscriptions/{SUB}/providers/Microsoft.Advisor/recommendations", FIXTURES["advisor"]))
        client = AdvisorManagementClient(credential=FictionalCredential(), subscription_id=SUB, transport=transport, retry_total=0)
        self.addCleanup(client.close)
        return AdvisorService(client=client, settings=SETTINGS), transport

    def graph(self, fixture="graph"):
        transport = FixtureTransport(("POST", "/providers/Microsoft.ResourceGraph/resources", FIXTURES[fixture]))
        client = ResourceGraphClient(credential=FictionalCredential(), transport=transport, retry_total=0)
        self.addCleanup(client.close)
        return ResourceGraphService(client=client, settings=SETTINGS), transport

    def test_cost_actual_summary_request_and_response(self):
        svc, transport = self.cost("cost_summary")
        result = svc.get_cost_summary()
        self.assertEqual((result["total_cost"], result["currency"]), (100.0, "EUR"))
        self.assertEqual(result["scope"], f"/subscriptions/{SUB}")
        body = transport.calls[0][2]
        self.assertEqual(body["type"], "ActualCost")
        self.assertEqual(body["dataset"]["granularity"], "Monthly")
        self.assertTrue(body["timePeriod"]["from"].startswith("2026-01-01"))
        self.assertTrue(body["timePeriod"]["to"].startswith("2026-01-31"))

    def test_cost_grouped_query_serializes_none_granularity(self):
        scope = f"/subscriptions/{SUB}/resourceGroups/demo-rg"
        svc, transport = self.cost("cost_grouped", scope=scope)
        result = svc.get_top_cost_drivers(resource_group="demo-rg")
        self.assertEqual(result["top_drivers"][0], {"name":"Compute","cost":60.0,"percentage":60.0})
        self.assertEqual(result["total_cost"], 100.0)
        body = transport.calls[0][2]
        self.assertEqual(body["dataset"]["granularity"], "None")
        self.assertEqual(body["dataset"]["grouping"][0]["name"], "ServiceName")

    def test_cost_tag_filter_serialization(self):
        svc, transport = self.cost("cost_summary")
        result = svc.get_cost_by_tag("Environment", "Demo")
        self.assertEqual(result["total_cost"], 100.0)
        self.assertEqual(transport.calls[0][2]["dataset"]["filter"]["tags"]["values"], ["Demo"])

    def test_cost_malformed_mixed_and_paged_fail_closed(self):
        for fixture in ("cost_malformed", "cost_mixed", "cost_paged"):
            with self.subTest(fixture=fixture):
                svc, transport = self.cost(fixture)
                with self.assertRaises(ValueError):
                    svc.get_cost_summary()
                self.assertEqual(len(transport.calls), 1)

    def test_advisor_flattened_response_and_filter(self):
        svc, transport = self.advisor()
        result = svc.get_cost_recommendations("demo-rg")
        row = result["recommendations"][0]
        self.assertEqual(row["category"], "Cost")
        self.assertEqual(row["resource_metadata"]["resource_id"], FIXTURES["graph"]["data"][0]["id"])
        self.assertEqual(row["provider_savings"]["amount"], 120.0)
        self.assertEqual(row["provider_savings"]["period"], "unknown")
        self.assertIsNone(row["estimated_monthly_savings"])
        self.assertIn("ResourceGroup eq 'demo-rg'", unquote(transport.calls[0][3]).replace("+", " "))

    def test_advisor_invalid_filter_no_request(self):
        svc, transport = self.advisor()
        with self.assertRaises(ValueError):
            svc.get_cost_recommendations("x' or '1")
        self.assertEqual(transport.calls, [])

    def test_graph_object_array_and_scope(self):
        svc, transport = self.graph()
        result = svc.get_unused_disks()
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["unused_disks"][0]["name"], "demo-disk")
        body = transport.calls[0][2]
        self.assertEqual(body["subscriptions"], [SUB])
        self.assertEqual(body["options"]["resultFormat"], "objectArray")
        self.assertIn("properties.diskState", body["query"])
        self.assertIn("tostring(managedBy)", body["query"])

    def test_graph_partial_and_inconsistent_counts_rejected(self):
        for fixture in ("graph_partial", "graph_bad_count"):
            with self.subTest(fixture=fixture):
                svc, _ = self.graph(fixture)
                with self.assertRaises(ValueError):
                    svc.get_unused_disks()

    def test_graph_empty_response(self):
        svc, _ = self.graph("graph_empty")
        self.assertEqual(svc.get_unused_disks(), {"unused_disks": [], "count": 0})

    def test_actual_sdk_adapters_dispatch_without_provider_network(self):
        cost, cost_transport = self.cost("cost_summary")
        advisor, advisor_transport = self.advisor()
        graph, graph_transport = self.graph()
        handlers = ToolHandlers(cost=cost, advisor=advisor, graph=graph, subscription_id=SUB)
        self.assertEqual(json.loads(handlers.dispatch("get_cost_summary", {}))["total_cost"], 100.0)
        self.assertEqual(json.loads(handlers.dispatch("get_advisor_cost_recommendations", {}))["total_recommendations"], 1)
        self.assertIn("error", json.loads(handlers.dispatch("get_idle_resources", {"subscription_id": "other"})))
        self.assertEqual(len(cost_transport.calls), 1)
        self.assertEqual(len(advisor_transport.calls), 1)
        self.assertEqual(len(graph_transport.calls), 0)


if __name__ == "__main__":
    unittest.main()
