"""Bounded, stateless per-question Responses orchestration."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Protocol

from ..tools.definitions import TOOL_DEFINITIONS
from .prompts import SYSTEM_PROMPT

MAX_REQUESTS = 5
MAX_TOOL_CALLS = 8
MAX_ARGUMENT_BYTES = 4096
MAX_TOOL_OUTPUT_BYTES = 32768
MAX_CONTEXT_BYTES = 131072
MAX_QUESTION_BYTES = 4096
MAX_OUTPUT_TOKENS = 2000

SCHEMAS = {tool["name"]: tool["parameters"] for tool in TOOL_DEFINITIONS}


class OrchestrationError(RuntimeError):
    """No completed answer can be trusted from this attempt."""


class ResponseProvider(Protocol):
    def respond(self, items: list[dict], tools: list[dict]) -> dict: ...


class Dispatcher(Protocol):
    def dispatch(self, function_name: str, arguments: dict[str, Any]) -> str: ...


def _json_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"))


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("Non-finite JSON constant")


def _parse_json(value):
    return json.loads(value, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)


def _arguments(name: str, raw: str) -> dict:
    if name not in SCHEMAS:
        raise ValueError("Tool not allowed")
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_ARGUMENT_BYTES:
        raise ValueError("Invalid arguments size")
    args = _parse_json(raw)
    if not isinstance(args, dict):
        raise ValueError("Arguments must be an object")
    schema = SCHEMAS[name]
    props = schema["properties"]
    if set(args) - set(props) or set(schema.get("required", [])) - set(args):
        raise ValueError("Unexpected or missing arguments")
    for key, value in args.items():
        spec = props[key]
        kind = spec["type"]
        if kind == "string":
            if not isinstance(value, str) or not value.strip() or len(value) > 256 or any(ord(c) < 32 for c in value):
                raise ValueError("Invalid string argument")
            if key == "resource_group" and (not re.fullmatch(r"[\w.()-]{1,90}", value) or value.endswith(".")):
                raise ValueError("Invalid resource group")
        elif kind == "integer":
            if type(value) is not int:
                raise ValueError("Invalid integer argument")
            if not spec.get("minimum", 1) <= value <= spec.get("maximum", 365):
                raise ValueError("Integer out of range")
        elif kind == "boolean":
            if type(value) is not bool:
                raise ValueError("Invalid boolean argument")
        else:
            raise ValueError("Unsupported schema type")
        if "enum" in spec and value not in spec["enum"]:
            raise ValueError("Invalid enum argument")
    return args


class AgentRunner:
    """Application owns orchestration; model has no execution authority.

    Each chat is independent, including within interactive CLI mode. No remote
    agent is created/reused, no response IDs are persisted, no prior-turn data
    is replayed. Within a question all output items are replayed in order.
    """

    def __init__(self, *, provider: ResponseProvider | None = None, handlers: Dispatcher | None = None):
        if provider is None and handlers is None:
            from .foundry import FoundryResponsesProvider
            from ..tools.handlers import ToolHandlers
            handlers = ToolHandlers()
            provider = FoundryResponsesProvider.from_settings()
        elif provider is None or handlers is None:
            raise ValueError("Inject both provider and handlers together.")
        self._provider = provider
        self._handlers = handlers

    def close(self):
        close = getattr(self._provider, "close", None)
        if close:
            close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def chat(self, user_message: str) -> str:
        if not isinstance(user_message, str) or not user_message.strip() or len(user_message.encode("utf-8")) > MAX_QUESTION_BYTES:
            raise OrchestrationError("Question is empty or exceeds the input limit.")
        items = [{"role": "user", "content": user_message}]
        tools = [{"type": "function", **deepcopy(tool), "strict": False} for tool in TOOL_DEFINITIONS]
        seen: set[str] = set()
        # A completed response is the only successful terminal state.
        for index in range(MAX_REQUESTS):
            if _json_size(items) > MAX_CONTEXT_BYTES:
                raise OrchestrationError("Context limit exceeded.")
            try:
                response = self._provider.respond(deepcopy(items), deepcopy(tools))
                if response.get("status") != "completed":
                    raise OrchestrationError("Provider did not complete the response.")
                output = response.get("output")
                if not isinstance(output, list) or not output or _json_size(output) > MAX_CONTEXT_BYTES:
                    raise OrchestrationError("Invalid or oversized provider output.")
                if any(not isinstance(item, dict) or item.get("type") not in {"message", "reasoning", "function_call"} for item in output):
                    raise OrchestrationError("Unsupported provider output item.")
                calls = [item for item in output if item["type"] == "function_call"]
                if not calls:
                    text = []
                    for item in output:
                        if item["type"] != "message":
                            continue
                        if item.get("role") != "assistant" or not isinstance(item.get("content"), list):
                            raise OrchestrationError("Invalid assistant message.")
                        for part in item["content"]:
                            if not isinstance(part, dict) or part.get("type") != "output_text" or not isinstance(part.get("text"), str):
                                raise OrchestrationError("Provider returned no usable final text.")
                            text.append(part["text"])
                    answer = "\n".join(text).strip()
                    if not answer:
                        raise OrchestrationError("Provider returned no final text.")
                    return answer
                if index == MAX_REQUESTS - 1 or len(seen) + len(calls) > MAX_TOOL_CALLS:
                    raise OrchestrationError("Tool-call or response-round budget exhausted.")
                # Validate the whole batch before any dispatch. Duplicate IDs
                # cannot be replayed, even across rounds.
                prepared = []
                batch_ids = set()
                for call in calls:
                    cid = call.get("call_id")
                    name = call.get("name")
                    if not isinstance(cid, str) or not cid or len(cid) > 128 or cid in seen or cid in batch_ids:
                        raise OrchestrationError("Invalid or duplicate tool call identifier.")
                    if not isinstance(name, str) or name not in SCHEMAS:
                        raise OrchestrationError("Provider requested a tool outside the allowlist.")
                    try:
                        args = _arguments(name, call.get("arguments"))
                    except (ValueError, TypeError, UnicodeError, RecursionError):
                        raise OrchestrationError("Provider supplied invalid tool arguments.") from None
                    prepared.append((cid, name, args))
                    batch_ids.add(cid)
                items.extend(output)
                if _json_size(items) > MAX_CONTEXT_BYTES:
                    raise OrchestrationError("Context limit exceeded before tool dispatch.")
                for cid, name, args in prepared:
                    seen.add(cid)
                    raw = self._handlers.dispatch(name, args)
                    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_TOOL_OUTPUT_BYTES:
                        raise OrchestrationError("Tool result exceeds the evidence limit.")
                    evidence = _parse_json(raw)
                    if not isinstance(evidence, dict) or "error" in evidence:
                        raise OrchestrationError("Tool failed; no financial answer returned.")
                    items.append({"type": "function_call_output", "call_id": cid, "output": raw})
                    if _json_size(items) > MAX_CONTEXT_BYTES:
                        raise OrchestrationError("Context limit exceeded.")
            except OrchestrationError:
                raise
            except Exception:
                # Do not leak provider error text, resource data or credentials.
                raise OrchestrationError("Provider or tool execution failed; no answer returned.") from None
        raise OrchestrationError("Response budget exhausted.")
