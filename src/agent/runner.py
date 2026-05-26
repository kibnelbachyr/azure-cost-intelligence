"""
Azure AI Foundry agent runner.

Creates (or reuses) an agent with all cost-optimisation tools registered,
then drives the run loop: send message → poll for completion → handle tool
calls → return final answer.

SDK: azure-ai-projects  (>= 1.0.0b11)
Docs: https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/sdk-overview
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AgentThread,
    FunctionTool,
    MessageRole,
    RequiredFunctionToolCall,
    RunStatus,
    SubmitToolOutputsAction,
    ThreadMessage,
    ToolOutput,
    ToolSet,
)
from azure.identity import DefaultAzureCredential, ClientSecretCredential

from ..config import get_settings
from ..tools.definitions import TOOL_DEFINITIONS
from ..tools.handlers import ToolHandlers
from .prompts import SYSTEM_PROMPT

log = logging.getLogger(__name__)

# How long to wait between run-status polls (seconds)
_POLL_INTERVAL = 2.0
# Maximum number of poll iterations before giving up
_MAX_POLLS = 120  # 4 minutes


def _build_credential():
    cfg = get_settings()
    if cfg.use_managed_identity:
        return DefaultAzureCredential()
    return ClientSecretCredential(
        tenant_id=cfg.azure_tenant_id,
        client_id=cfg.azure_client_id,
        client_secret=cfg.azure_client_secret,
    )


class AgentRunner:
    """
    Manages the lifecycle of the Azure Cost Optimisation AI agent.

    Typical usage::

        runner = AgentRunner()
        response = runner.chat("Where am I overspending this month?")
        print(response)
    """

    def __init__(self) -> None:
        cfg = get_settings()
        self._cfg = cfg
        self._handlers = ToolHandlers()

        self._project_client = AIProjectClient.from_connection_string(
            credential=_build_credential(),
            conn_str=cfg.azure_ai_project_connection_string,
        )

        # Build the ToolSet from our JSON schema definitions
        function_tools = [
            FunctionTool(
                name=td["name"],
                description=td["description"],
                parameters=td["parameters"],
            )
            for td in TOOL_DEFINITIONS
        ]
        self._toolset = ToolSet()
        self._toolset.add(function_tools)

        self._agent = self._get_or_create_agent()
        log.info("Agent ready: %s", self._agent.id)

    # ── agent management ──────────────────────────────────────────────────────

    def _get_or_create_agent(self):
        """
        Look for an existing agent named 'azure-cost-advisor'.
        Create a new one if none exists.
        """
        agents_client = self._project_client.agents

        existing = list(agents_client.list_agents())
        for a in existing:
            if a.name == "azure-cost-advisor":
                log.info("Reusing existing agent %s", a.id)
                return a

        log.info("Creating new agent 'azure-cost-advisor'")
        return agents_client.create_agent(
            model=self._cfg.azure_openai_deployment_name,
            name="azure-cost-advisor",
            instructions=SYSTEM_PROMPT,
            tools=self._toolset.definitions,
        )

    # ── public interface ──────────────────────────────────────────────────────

    def create_thread(self) -> AgentThread:
        """Create a new conversation thread."""
        return self._project_client.agents.create_thread()

    def chat(
        self,
        user_message: str,
        thread_id: str | None = None,
    ) -> str:
        """
        Send a message to the agent and return its final text response.

        Args:
            user_message: The user's natural-language question.
            thread_id:    Reuse an existing thread for multi-turn conversation.
                          If None, a new thread is created.
        Returns:
            The agent's final answer as a string.
        """
        agents_client = self._project_client.agents

        # Get or create thread
        if thread_id:
            thread = agents_client.get_thread(thread_id)
        else:
            thread = agents_client.create_thread()

        # Add user message
        agents_client.create_message(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=user_message,
        )

        # Start a run
        run = agents_client.create_run(
            thread_id=thread.id,
            assistant_id=self._agent.id,
        )

        log.info("Run %s started for thread %s", run.id, thread.id)

        # Poll until terminal state
        run = self._poll_run(agents_client, thread.id, run.id)

        # Extract final assistant message
        return self._extract_response(agents_client, thread.id)

    # ── internal run loop ─────────────────────────────────────────────────────

    def _poll_run(self, agents_client, thread_id: str, run_id: str):
        """
        Poll the run until it completes, handling tool calls along the way.
        """
        polls = 0
        while polls < _MAX_POLLS:
            run = agents_client.get_run(thread_id=thread_id, run_id=run_id)
            status = run.status

            log.debug("Run %s status: %s", run_id, status)

            if status == RunStatus.REQUIRES_ACTION:
                run = self._handle_tool_calls(agents_client, thread_id, run)

            elif status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.EXPIRED):
                if status != RunStatus.COMPLETED:
                    log.error("Run %s ended with status: %s", run_id, status)
                return run

            polls += 1
            time.sleep(_POLL_INTERVAL)

        raise TimeoutError(f"Run {run_id} did not complete within the allowed time.")

    def _handle_tool_calls(self, agents_client, thread_id: str, run):
        """Execute all pending tool calls and submit results."""
        action: SubmitToolOutputsAction = run.required_action
        tool_outputs: list[ToolOutput] = []

        for tool_call in action.submit_tool_outputs.tool_calls:
            if not isinstance(tool_call, RequiredFunctionToolCall):
                continue

            fn_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments or "{}")

            log.info("Calling tool: %s(%s)", fn_name, list(arguments.keys()))
            output = self._handlers.dispatch(fn_name, arguments)

            tool_outputs.append(
                ToolOutput(tool_call_id=tool_call.id, output=output)
            )

        run = agents_client.submit_tool_outputs_to_run(
            thread_id=thread_id,
            run_id=run.id,
            tool_outputs=tool_outputs,
        )
        return run

    def _extract_response(self, agents_client, thread_id: str) -> str:
        """Return the latest assistant message from the thread."""
        messages = agents_client.list_messages(thread_id=thread_id)
        for msg in messages.data:
            if msg.role == MessageRole.ASSISTANT:
                parts = []
                for block in msg.content:
                    if hasattr(block, "text"):
                        parts.append(block.text.value)
                return "\n".join(parts)
        return "(No response from agent)"

    # ── convenience helpers ───────────────────────────────────────────────────

    def delete_agent(self) -> None:
        """Delete the agent from Foundry (useful for cleanup in tests)."""
        self._project_client.agents.delete_agent(self._agent.id)
        log.info("Agent %s deleted", self._agent.id)
