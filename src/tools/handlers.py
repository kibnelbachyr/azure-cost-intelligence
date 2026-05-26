"""
Tool handler implementations.

Each method maps 1-to-1 with a function name in definitions.py.
The AgentRunner calls dispatch() with the function name and parsed arguments,
then serialises the result to JSON before returning it to the agent.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ..services.cost_management import CostManagementService
from ..services.advisor import AdvisorService
from ..services.resource_graph import ResourceGraphService
from ..recommendations.engine import RecommendationEngine

log = logging.getLogger(__name__)


class ToolHandlers:
    """
    Instantiates the underlying service clients once and exposes a single
    dispatch() entry point that the agent runner calls during tool execution.
    """

    def __init__(self) -> None:
        self._cost = CostManagementService()
        self._advisor = AdvisorService()
        self._graph = ResourceGraphService()
        self._engine = RecommendationEngine()

    # ── dispatcher ────────────────────────────────────────────────────────────

    def dispatch(self, function_name: str, arguments: dict[str, Any]) -> str:
        """
        Route a tool call to the correct handler.

        Returns:
            JSON string — the agent will receive this as the tool result.
        """
        handler = {
            "get_cost_summary": self._get_cost_summary,
            "get_top_cost_drivers": self._get_top_cost_drivers,
            "get_cost_by_tag": self._get_cost_by_tag,
            "get_advisor_cost_recommendations": self._get_advisor_cost_recommendations,
            "correlate_cost_and_advisor": self._correlate_cost_and_advisor,
            "get_idle_resources": self._get_idle_resources,
            "get_cost_trend": self._get_cost_trend,
        }.get(function_name)

        if handler is None:
            return json.dumps({"error": f"Unknown tool: {function_name}"})

        try:
            result = handler(**arguments)
            return json.dumps(result, default=str)
        except Exception as exc:
            log.exception("Tool '%s' raised an error", function_name)
            return json.dumps({"error": str(exc), "tool": function_name})

    # ── individual handlers ───────────────────────────────────────────────────

    def _get_cost_summary(
        self,
        subscription_id: str | None = None,
        resource_group: str | None = None,
        lookback_days: int = 30,
        granularity: str = "Monthly",
    ) -> dict[str, Any]:
        return self._cost.get_cost_summary(
            subscription_id=subscription_id,
            resource_group=resource_group,
            lookback_days=lookback_days,
            granularity=granularity,
        )

    def _get_top_cost_drivers(
        self,
        subscription_id: str | None = None,
        resource_group: str | None = None,
        lookback_days: int = 30,
        group_by: str = "ServiceName",
        limit: int = 10,
    ) -> dict[str, Any]:
        return self._cost.get_top_cost_drivers(
            subscription_id=subscription_id,
            resource_group=resource_group,
            lookback_days=lookback_days,
            group_by=group_by,
            limit=limit,
        )

    def _get_cost_by_tag(
        self,
        tag_name: str,
        tag_value: str,
        subscription_id: str | None = None,
        lookback_days: int = 30,
    ) -> dict[str, Any]:
        return self._cost.get_cost_by_tag(
            tag_name=tag_name,
            tag_value=tag_value,
            subscription_id=subscription_id,
            lookback_days=lookback_days,
        )

    def _get_advisor_cost_recommendations(
        self,
        resource_group: str | None = None,
    ) -> dict[str, Any]:
        return self._advisor.get_cost_recommendations(resource_group=resource_group)

    def _get_idle_resources(
        self,
        subscription_id: str | None = None,  # reserved for future multi-sub support
    ) -> dict[str, Any]:
        idle_vms = self._graph.get_idle_vms()
        unused_disks = self._graph.get_unused_disks()
        unused_pips = self._graph.get_unattached_public_ips()
        return {
            "idle_vms": idle_vms,
            "unused_disks": unused_disks,
            "unattached_public_ips": unused_pips,
            "summary": {
                "idle_vm_count": idle_vms["count"],
                "unused_disk_count": unused_disks["count"],
                "unattached_ip_count": unused_pips["count"],
            },
        }

    def _get_cost_trend(
        self,
        subscription_id: str | None = None,
        lookback_days: int = 90,
    ) -> dict[str, Any]:
        return self._cost.get_cost_trend(
            subscription_id=subscription_id,
            lookback_days=lookback_days,
        )

    def _correlate_cost_and_advisor(
        self,
        subscription_id: str | None = None,
        resource_group: str | None = None,
        lookback_days: int = 30,
        include_idle_resources: bool = True,
    ) -> dict[str, Any]:
        """
        Orchestrated call: runs cost + advisor + (optionally) idle resource
        queries in sequence, then feeds results through the recommendation
        engine to produce a prioritised list.
        """
        cost_summary = self._cost.get_cost_summary(
            subscription_id=subscription_id,
            resource_group=resource_group,
            lookback_days=lookback_days,
        )
        top_drivers = self._cost.get_top_cost_drivers(
            subscription_id=subscription_id,
            resource_group=resource_group,
            lookback_days=lookback_days,
        )
        advisor_data = self._advisor.get_cost_recommendations(resource_group=resource_group)

        idle_data: dict[str, Any] = {}
        if include_idle_resources:
            idle_vms = self._graph.get_idle_vms()
            unused_disks = self._graph.get_unused_disks()
            unused_pips = self._graph.get_unattached_public_ips()
            idle_data = {
                "idle_vms": idle_vms,
                "unused_disks": unused_disks,
                "unused_pips": unused_pips,
            }

        recommendations = self._engine.correlate(
            cost_summary=cost_summary,
            top_drivers=top_drivers,
            advisor_data=advisor_data,
            idle_resources=idle_data,
        )

        total_potential_savings = sum(
            r["estimated_monthly_savings"] or 0
            for r in recommendations
            if r.get("estimated_monthly_savings")
        )

        return {
            "cost_summary": cost_summary,
            "top_drivers": top_drivers,
            "recommendations": recommendations,
            "total_potential_monthly_savings": round(total_potential_savings, 2),
            "quick_wins": [r for r in recommendations if r.get("is_quick_win")],
        }
