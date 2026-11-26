"""
Recommendation Engine — correlates Cost Management data with Advisor
recommendations and produces a prioritised, enriched recommendation list
that is both human-readable and easy for the LLM to cite.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# Effort scoring heuristics based on Advisor recommendation type keywords
_EFFORT_KEYWORDS: dict[str, list[str]] = {
    "low": [
        "right-size", "resize", "shutdown", "auto-shutdown", "delete unused",
        "remove unattached", "reserved instance", "savings plan",
        "idle", "unused", "stop",
    ],
    "medium": [
        "migrate", "upgrade", "change tier", "switch", "enable",
        "move", "consolidate",
    ],
    "high": [
        "re-architect", "refactor", "redesign", "renegotiate",
        "multi-region", "major change",
    ],
}

_RISK_KEYWORDS: dict[str, list[str]] = {
    "low": ["snapshot", "backup", "reserved", "savings plan", "idle", "unattached", "unused"],
    "medium": ["resize", "right-size", "change tier", "stop", "deallocate"],
    "high": ["delete", "remove", "migrate", "renegotiate"],
}


def _classify_effort(text: str) -> str:
    lower = text.lower()
    for level in ("low", "medium", "high"):
        if any(kw in lower for kw in _EFFORT_KEYWORDS[level]):
            return level
    return "medium"


def _classify_risk(text: str) -> str:
    """Conservative heuristic: destructive language takes precedence."""
    lower = text.lower()
    for level in ("high", "medium", "low"):
        if any(kw in lower for kw in _RISK_KEYWORDS[level]):
            return level
    return "medium"


def _priority_score(rec: "Recommendation") -> float:
    """Higher is more urgent."""
    impact_weight = {"High": 3.0, "Medium": 2.0, "Low": 1.0}
    effort_weight = {"low": 1.5, "medium": 1.0, "high": 0.5}

    savings = rec.estimated_monthly_savings or 0.0
    impact = impact_weight.get(rec.impact or "Low", 1.0)
    effort = effort_weight.get(rec.effort, 1.0)

    return round(savings * impact * effort, 2)


@dataclass
class Recommendation:
    id: str
    title: str
    description: str
    category: str
    impact: str
    effort: str          # low | medium | high
    risk: str            # low | medium | high
    estimated_monthly_savings: float | None
    savings_currency: str
    recommended_actions: list[str] = field(default_factory=list)
    impacted_resource: str | None = None
    is_quick_win: bool = False
    trade_offs: list[str] = field(default_factory=list)
    priority_score: float = 0.0
    source: str = "Azure Advisor"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "impact": self.impact,
            "effort": self.effort,
            "risk": self.risk,
            "estimated_monthly_savings": self.estimated_monthly_savings,
            "savings_currency": self.savings_currency,
            "recommended_actions": self.recommended_actions,
            "impacted_resource": self.impacted_resource,
            "is_quick_win": self.is_quick_win,
            "trade_offs": self.trade_offs,
            "priority_score": self.priority_score,
            "source": self.source,
        }


class RecommendationEngine:
    """
    Takes raw cost data + raw Advisor recommendations and produces a
    ranked list of Recommendation objects with enriched metadata.
    """

    def correlate(
        self,
        cost_summary: dict[str, Any],
        top_drivers: dict[str, Any],
        advisor_data: dict[str, Any],
        idle_resources: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Main entry point.  Returns a list of recommendation dicts,
        sorted by priority_score descending.

        Args:
            cost_summary:   Output of CostManagementService.get_cost_summary()
            top_drivers:    Output of CostManagementService.get_top_cost_drivers()
            advisor_data:   Output of AdvisorService.get_cost_recommendations()
            idle_resources: (optional) ResourceGraphService results
        """
        recs: list[Recommendation] = []

        recs.extend(self._from_advisor(advisor_data))
        recs.extend(self._from_idle_resources(idle_resources or {}))
        recs.extend(self._from_cost_drivers(top_drivers, cost_summary))

        # Deduplicate by similar title + resource
        recs = self._deduplicate(recs)

        # Score and sort
        for r in recs:
            r.priority_score = _priority_score(r)
        recs.sort(key=lambda r: r.priority_score, reverse=True)

        # Mark quick wins: low effort + low/medium risk + meaningful savings
        for r in recs:
            r.is_quick_win = (
                r.effort == "low"
                and r.risk in ("low", "medium")
                and (r.estimated_monthly_savings or 0) > 0
            )

        return [r.to_dict() for r in recs]

    # ── private builders ──────────────────────────────────────────────────────

    def _from_advisor(self, advisor_data: dict[str, Any]) -> list[Recommendation]:
        result = []
        for raw in advisor_data.get("recommendations", []):
            problem = raw.get("problem") or ""
            solution = raw.get("solution") or ""
            combined_text = f"{problem} {solution}"

            effort = _classify_effort(combined_text)
            risk = _classify_risk(combined_text)

            trade_offs = []
            if effort == "medium" or risk == "medium":
                trade_offs.append("Validate change in a non-production environment first.")
            if "delete" in combined_text.lower() or "remove" in combined_text.lower():
                trade_offs.append("Ensure resource is not needed before deletion.")

            rec = Recommendation(
                id=raw.get("name", ""),
                title=problem or "Cost Optimization Opportunity",
                description=solution or "",
                category=raw.get("category", "Cost"),
                impact=raw.get("impact", "Low"),
                effort=effort,
                risk=risk,
                estimated_monthly_savings=raw.get("estimated_monthly_savings"),
                savings_currency=raw.get("savings_currency", "USD"),
                recommended_actions=[solution] if solution else [],
                impacted_resource=raw.get("impacted_value"),
                trade_offs=trade_offs,
            )
            result.append(rec)
        return result

    def _from_idle_resources(self, idle_data: dict[str, Any]) -> list[Recommendation]:
        result = []

        for vm in idle_data.get("idle_vms", {}).get("idle_vms", []):
            rec = Recommendation(
                id=f"idle-vm-{vm.get('name', '')}",
                title=f"Idle VM: {vm.get('name', 'Unknown')}",
                description=(
                    f"VM '{vm.get('name')}' in '{vm.get('resourceGroup')}' "
                    f"is {vm.get('powerState', 'stopped')} but still incurring disk charges."
                ),
                category="Cost",
                impact="Medium",
                effort="low",
                risk="high",
                estimated_monthly_savings=None,
                savings_currency="USD",
                recommended_actions=[
                    f"Delete or deallocate VM '{vm.get('name')}' if no longer needed.",
                    "Consider auto-shutdown schedule for dev/test VMs.",
                ],
                impacted_resource=vm.get("id"),
                trade_offs=["Confirm ownership, dependencies, backup/recovery and business impact; obtain explicit approval before shutdown or deletion."],
            )
            result.append(rec)

        for disk in idle_data.get("unused_disks", {}).get("unused_disks", []):
            size_gb = disk.get("sizeGb", 0)
            # Rough estimate: P10 managed disk ≈ $0.04/GB/month
            estimated = round(size_gb * 0.04, 2)
            rec = Recommendation(
                id=f"unused-disk-{disk.get('name', '')}",
                title=f"Unattached Managed Disk: {disk.get('name', 'Unknown')}",
                description=(
                    f"Disk '{disk.get('name')}' ({size_gb} GB, {disk.get('sku', 'Standard')}) "
                    f"in '{disk.get('resourceGroup')}' has no attached VM."
                ),
                category="Cost",
                impact="Low",
                effort="low",
                risk="high",
                estimated_monthly_savings=estimated,
                savings_currency="USD",
                recommended_actions=[
                    f"Snapshot and delete disk '{disk.get('name')}' if data is no longer needed.",
                ],
                impacted_resource=disk.get("id"),
                trade_offs=["Verify ownership, dependencies, retention and recoverability before any deletion; obtain explicit approval."],
            )
            result.append(rec)

        for pip in idle_data.get("unused_pips", {}).get("unattached_public_ips", []):
            # Standard PIP ≈ $0.005/hour = ~$3.60/month
            estimated = 3.60
            rec = Recommendation(
                id=f"unused-pip-{pip.get('name', '')}",
                title=f"Unattached Public IP: {pip.get('name', 'Unknown')}",
                description=(
                    f"Public IP '{pip.get('name')}' ({pip.get('sku', 'Standard')}) "
                    f"in '{pip.get('resourceGroup')}' is not associated with any resource."
                ),
                category="Cost",
                impact="Low",
                effort="low",
                risk="high",
                estimated_monthly_savings=estimated,
                savings_currency="USD",
                recommended_actions=[
                    f"Delete public IP '{pip.get('name')}' only after reviewing ownership and dependencies.",
                ],
                impacted_resource=pip.get("id"),
                trade_offs=["Confirm external consumers, allowlists, DNS and recovery requirements; obtain explicit approval."],
            )
            result.append(rec)

        return result

    def _from_cost_drivers(
        self,
        top_drivers: dict[str, Any],
        cost_summary: dict[str, Any],
    ) -> list[Recommendation]:
        """
        Synthesise high-level cost observations from the top-N spend drivers.
        These are not direct Advisor findings but give the agent context about
        *where* money is going so it can give better narrative advice.
        """
        result = []
        total = cost_summary.get("total_cost", 1) or 1
        currency = cost_summary.get("currency", "USD")

        for driver in top_drivers.get("top_drivers", [])[:3]:
            pct = driver.get("percentage", 0)
            if pct < 5:
                continue  # not significant enough to call out separately

            rec = Recommendation(
                id=f"top-spend-{driver['name'].replace(' ', '-').lower()}",
                title=f"High Spend: {driver['name']} ({pct}% of total)",
                description=(
                    f"{driver['name']} accounts for {driver['cost']} {currency} "
                    f"({pct}% of total spend of {total} {currency} in the period). "
                    "Review whether consumption is expected or can be optimised."
                ),
                category="Cost",
                impact="High" if pct > 25 else "Medium",
                effort="medium",
                risk="low",
                estimated_monthly_savings=None,
                savings_currency=currency,
                recommended_actions=[
                    f"Review {driver['name']} usage in Azure Portal Cost Analysis.",
                    "Compare actual vs. budgeted spend.",
                    "Identify if any resources in this service are idle or over-provisioned.",
                ],
                trade_offs=[],
                source="Cost Management Analysis",
            )
            result.append(rec)

        return result

    def _deduplicate(self, recs: list[Recommendation]) -> list[Recommendation]:
        """Remove duplicate recommendations based on impacted resource."""
        seen: set[str] = set()
        unique = []
        for r in recs:
            key = f"{r.impacted_resource or r.id}"
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique
