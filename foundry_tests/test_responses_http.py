"""Real Foundry + OpenAI clients, fabricated HTTP, no real credential."""
import json
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx2 as httpx
from azure.ai.projects import AIProjectClient
from azure.core.credentials import AccessToken

from src.agent.foundry import FoundryResponsesProvider
from src.agent.runner import AgentRunner, OrchestrationError
from src.agent.prompts import SYSTEM_PROMPT

FIX = json.loads((Path(__file__).parents[1]/"tests"/"fixtures"/"responses-v1.json").read_text())


class Credential:
    def get_token(self, *scopes, **kwargs):
        return AccessToken("fictional-token", 4102444800)


class Dispatcher:
    def __init__(self): self.calls = []
    def dispatch(self, name, args):
        self.calls.append((name, args))
        return '{"currency":"EUR","total_cost":100}'


class FoundryContracts(unittest.TestCase):
    def setUp(self):
        for target, attr in [(socket.socket,"connect"),(socket.socket,"connect_ex"),(socket,"getaddrinfo")]:
            guard = patch.object(target, attr, side_effect=AssertionError("Network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)

    def test_real_client_serializes_stateless_function_roundtrip(self):
        bodies = []
        def respond(request):
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.host, "example.services.ai.azure.com")
            self.assertTrue(request.url.path.endswith("/api/projects/demo/openai/v1/responses"))
            self.assertEqual(request.headers.get("authorization"), "Bearer fictional-token")
            bodies.append(json.loads(request.content))
            self.assertLessEqual(len(bodies), 2)
            fixture = FIX["call" if len(bodies)==1 else "final"]
            return httpx.Response(200, json={"id":f"resp_{len(bodies)}","object":"response","created_at":1760000000,
                "model":"synthetic-model","parallel_tool_calls":False,"tools":[],"tool_choice":"auto",
                **fixture})
        client = httpx.Client(transport=httpx.MockTransport(respond))
        self.addCleanup(client.close)
        project = AIProjectClient(endpoint="https://example.services.ai.azure.com/api/projects/demo", credential=Credential())
        provider = FoundryResponsesProvider(project, model="synthetic-model", http_client=client)
        self.addCleanup(provider.close)
        dispatcher = Dispatcher()
        result = AgentRunner(provider=provider, handlers=dispatcher).chat("Cost?")
        self.assertIn("EUR 100", result)
        self.assertEqual(dispatcher.calls, [("get_cost_summary", {"lookback_days":30})])
        self.assertEqual(len(bodies),2)
        for body in bodies:
            self.assertFalse(body["store"])
            self.assertFalse(body["parallel_tool_calls"])
            self.assertEqual(body["instructions"], SYSTEM_PROMPT)
            self.assertEqual(body["model"], "synthetic-model")
            self.assertEqual(body["max_output_tokens"], 2000)
            self.assertNotIn("previous_response_id", body)
            self.assertEqual(len(body["tools"]),7)
        self.assertEqual(bodies[1]["input"][1]["type"],"function_call")
        self.assertEqual(bodies[1]["input"][2]["call_id"],"call_demo")
        self.assertEqual(bodies[1]["input"][2]["type"],"function_call_output")

    def test_http_failure_does_not_retry_or_dispatch(self):
        calls = []
        def respond(request):
            calls.append(request.url.path)
            return httpx.Response(500,json={"error":{"message":"synthetic internal details","type":"server_error"}})
        client = httpx.Client(transport=httpx.MockTransport(respond))
        self.addCleanup(client.close)
        project = AIProjectClient(endpoint="https://example.services.ai.azure.com/api/projects/demo", credential=Credential())
        provider = FoundryResponsesProvider(project, model="synthetic-model", http_client=client)
        self.addCleanup(provider.close)
        dispatcher = Dispatcher()
        with self.assertRaises(OrchestrationError) as cm:
            AgentRunner(provider=provider, handlers=dispatcher).chat("Cost?")
        self.assertNotIn("internal details", str(cm.exception))
        self.assertEqual(len(calls),1)
        self.assertEqual(dispatcher.calls,[])
