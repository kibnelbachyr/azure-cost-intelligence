"""Deterministic orchestration without Azure or SDK imports."""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from src.agent.runner import AgentRunner, OrchestrationError, MAX_REQUESTS, MAX_TOOL_CALLS, MAX_TOOL_OUTPUT_BYTES

FIX = json.loads((Path(__file__).parent / "fixtures" / "responses-v1.json").read_text())


class Provider:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []
    def respond(self, items, tools):
        self.requests.append((deepcopy(items), deepcopy(tools)))
        if not self.responses:
            raise AssertionError("Unexpected request")
        return deepcopy(self.responses.pop(0))


class Tools:
    def __init__(self, output='{"total_cost":100,"currency":"EUR"}'):
        self.calls = []
        self.output = output
    def dispatch(self, name, args):
        self.calls.append((name, args))
        return self.output


def call(**changes):
    item = deepcopy(FIX["call"])
    item["output"][0].update(changes)
    return item


class OrchestrationTests(unittest.TestCase):
    def test_roundtrip_and_fresh_question(self):
        p, t = Provider(FIX["call"], FIX["final"], FIX["final"]), Tools()
        r = AgentRunner(provider=p, handlers=t)
        self.assertIn("EUR 100", r.chat("Cost?"))
        self.assertEqual(t.calls, [("get_cost_summary", {"lookback_days":30})])
        items = p.requests[1][0]
        self.assertEqual(items[1], FIX["call"]["output"][0])
        self.assertEqual(items[2]["call_id"], "call_demo")
        self.assertEqual(items[2]["type"], "function_call_output")
        self.assertEqual(len(p.requests[0][1]), 7)
        r.chat("New question")
        self.assertEqual(p.requests[2][0], [{"role":"user","content":"New question"}])

    def test_reasoning_item_replayed(self):
        first = deepcopy(FIX["call"])
        first["output"].insert(0, {"type":"reasoning","id":"rs_demo","encrypted_content":"fictional"})
        p = Provider(first, FIX["final"])
        AgentRunner(provider=p, handlers=Tools()).chat("Cost?")
        self.assertEqual(p.requests[1][0][1], first["output"][0])

    def test_invalid_arguments_and_unknown_tools_never_dispatched(self):
        variants = [call(name="delete_resource"), call(arguments="{"),
            call(arguments="[]"), call(arguments='{"lookback_days":true}'),
            call(arguments='{"lookback_days":366}'), call(arguments='{"lookback_days":1,"lookback_days":2}'),
            call(arguments='{"unknown":1}'), call(arguments='{"resource_group":"x\' or \'y"}'),
            call(name="get_cost_by_tag", arguments="{}"), call(arguments='{"granularity":"Weekly"}'),
            call(name="get_top_cost_drivers", arguments='{"limit":51}'),
            call(arguments='{"lookback_days":NaN}')]
        for item in variants:
            with self.subTest(item=item):
                t = Tools()
                with self.assertRaises(OrchestrationError):
                    AgentRunner(provider=Provider(item), handlers=t).chat("Cost?")
                self.assertEqual(t.calls, [])

    def test_batch_validated_before_any_dispatch(self):
        item = deepcopy(FIX["call"])
        item["output"].append(call(name="delete_resource", call_id="bad")["output"][0])
        t = Tools()
        with self.assertRaises(OrchestrationError):
            AgentRunner(provider=Provider(item), handlers=t).chat("Cost?")
        self.assertEqual(t.calls, [])

    def test_duplicate_call_id_across_rounds(self):
        t = Tools()
        with self.assertRaises(OrchestrationError):
            AgentRunner(provider=Provider(FIX["call"], FIX["call"]), handlers=t).chat("Cost?")
        self.assertEqual(len(t.calls), 1)

    def test_duplicate_call_id_in_batch(self):
        item = deepcopy(FIX["call"])
        item["output"] *= 2
        t = Tools()
        with self.assertRaises(OrchestrationError):
            AgentRunner(provider=Provider(item), handlers=t).chat("Cost?")
        self.assertEqual(t.calls, [])

    def test_round_budget_does_not_dispatch_final_batch(self):
        p = Provider(*(call(call_id=str(i)) for i in range(MAX_REQUESTS)))
        t = Tools()
        with self.assertRaises(OrchestrationError):
            AgentRunner(provider=p, handlers=t).chat("Cost?")
        self.assertEqual(len(p.requests), MAX_REQUESTS)
        self.assertEqual(len(t.calls), MAX_REQUESTS-1)

    def test_call_budget_rejects_whole_batch(self):
        item = {"status":"completed","output":[call(call_id=str(i))["output"][0] for i in range(MAX_TOOL_CALLS+1)]}
        t = Tools()
        with self.assertRaises(OrchestrationError):
            AgentRunner(provider=Provider(item), handlers=t).chat("Cost?")
        self.assertEqual(t.calls, [])

    def test_failed_incomplete_refusal_and_unknown_output(self):
        variants = [FIX["failed"], FIX["incomplete"], {"status":"completed","output":[]},
            {"status":"completed","output":[{"type":"web_search_call"}]},
            {"status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"refusal","refusal":"No"}]}]}]
        for item in variants:
            with self.subTest(item=item), self.assertRaises(OrchestrationError):
                AgentRunner(provider=Provider(item), handlers=Tools()).chat("Cost?")

    def test_tool_error_and_oversize_abort_without_final_answer(self):
        for output in ('{"error":"internal secret"}', "x"* (MAX_TOOL_OUTPUT_BYTES+1), "invalid"):
            p = Provider(FIX["call"], FIX["final"])
            with self.assertRaises(OrchestrationError) as cm:
                AgentRunner(provider=p, handlers=Tools(output)).chat("Cost?")
            self.assertNotIn("internal secret", str(cm.exception))
            self.assertEqual(len(p.requests), 1)

    def test_provider_exception_sanitized(self):
        p = Provider()
        with patch.object(p, "respond", side_effect=RuntimeError("private endpoint")):
            with self.assertRaises(OrchestrationError) as cm:
                AgentRunner(provider=p, handlers=Tools()).chat("Cost?")
        self.assertNotIn("private endpoint", str(cm.exception))

    def test_partial_injection_and_invalid_question(self):
        with self.assertRaises(ValueError):
            AgentRunner(provider=Provider())
        p = Provider()
        for q in ("", "x"*4097):
            with self.assertRaises(OrchestrationError):
                AgentRunner(provider=p, handlers=Tools()).chat(q)
        self.assertEqual(p.requests, [])
