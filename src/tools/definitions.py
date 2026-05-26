"""
JSON schema definitions for every tool the agent can call.
These are fed directly to the Azure AI Foundry agent as FunctionTool objects.
"""
from __future__ import annotations

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "get_cost_summary",
        "description": (
            "Returns the total cost and a time-series breakdown for an Azure subscription "
            "or resource group.  Use this first to understand overall spend before drilling down."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "subscription_id": {
                    "type": "string",
                    "description": "Azure subscription ID. Defaults to the configured subscription.",
                },
                "resource_group": {
                    "type": "string",
                    "description": "Limit scope to a specific resource group name (optional).",
                },
                "lookback_days": {
                    "type": "integer",
                    "description": "Number of days to look back (1–365). Default: 30.",
                    "default": 30,
                },
                "granularity": {
                    "type": "string",
                    "enum": ["Daily", "Monthly"],
                    "description": "Time-series granularity. Default: Monthly.",
                    "default": "Monthly",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_top_cost_drivers",
        "description": (
            "Returns the top N Azure services or resource groups ranked by spend in the given period. "
            "Use this to identify *where* money is going."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "subscription_id": {"type": "string"},
                "resource_group": {"type": "string"},
                "lookback_days": {"type": "integer", "default": 30},
                "group_by": {
                    "type": "string",
                    "enum": ["ServiceName", "ResourceGroupName", "ResourceId", "MeterCategory"],
                    "description": "Dimension to group costs by. Default: ServiceName.",
                    "default": "ServiceName",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of top drivers to return. Default: 10.",
                    "default": 10,
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_cost_by_tag",
        "description": (
            "Returns total spend for all resources that carry a specific tag key=value pair. "
            "Useful for cost allocation by team, project, or environment."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tag_name": {
                    "type": "string",
                    "description": "Tag key, e.g. 'Environment' or 'CostCenter'.",
                },
                "tag_value": {
                    "type": "string",
                    "description": "Tag value, e.g. 'Production' or 'Marketing'.",
                },
                "subscription_id": {"type": "string"},
                "lookback_days": {"type": "integer", "default": 30},
            },
            "required": ["tag_name", "tag_value"],
        },
    },
    {
        "name": "get_advisor_cost_recommendations",
        "description": (
            "Fetches Azure Advisor Cost recommendations for the subscription (or a resource group). "
            "Returns a prioritised list of optimisation opportunities with estimated monthly savings."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "resource_group": {
                    "type": "string",
                    "description": "Limit to a specific resource group (optional).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "correlate_cost_and_advisor",
        "description": (
            "Runs a full cost analysis + Advisor query and correlates the results into a ranked list "
            "of actionable optimisation recommendations with estimated savings, effort, and risk. "
            "This is the most comprehensive tool — call it when the user asks for a broad overview "
            "or 'top opportunities'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "subscription_id": {"type": "string"},
                "resource_group": {"type": "string"},
                "lookback_days": {"type": "integer", "default": 30},
                "include_idle_resources": {
                    "type": "boolean",
                    "description": "Also scan for idle VMs, unattached disks, and orphaned IPs.",
                    "default": True,
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_idle_resources",
        "description": (
            "Scans the subscription for idle or underutilised resources: "
            "deallocated VMs, unattached managed disks, and orphaned public IPs. "
            "Use when the user asks about waste or idle resources."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "subscription_id": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "get_cost_trend",
        "description": (
            "Returns daily cost data for the past N days to highlight spend trends, "
            "spikes, or anomalies. Use when the user asks about trends or month-over-month changes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "subscription_id": {"type": "string"},
                "lookback_days": {
                    "type": "integer",
                    "description": "Number of days to look back. Default: 90.",
                    "default": 90,
                },
            },
            "required": [],
        },
    },
]
