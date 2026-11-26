"""
Wrapper around the Azure Advisor REST API.

Retrieves cost-category recommendations and surfaces them in a normalised
format that is easy for the LLM to reason over.

Docs: https://learn.microsoft.com/en-us/azure/advisor/
SDK:  azure-mgmt-advisor
"""
from __future__ import annotations

import logging
from typing import Any

from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.mgmt.advisor import AdvisorManagementClient
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import get_settings
from ..financial_evidence import provider_savings, savings_evidence_summary

log = logging.getLogger(__name__)

# Advisor categories we care about.  Others: "HighAvailability", "Security",
# "OperationalExcellence", "Performance"
COST_CATEGORY = "Cost"
ALL_CATEGORIES = [COST_CATEGORY, "HighAvailability", "Security", "OperationalExcellence", "Performance"]

IMPACT_SCORE = {"High": 3, "Medium": 2, "Low": 1}


def _build_credential():
    cfg = get_settings()
    if cfg.use_managed_identity:
        return DefaultAzureCredential()
    return ClientSecretCredential(
        tenant_id=cfg.azure_tenant_id,
        client_id=cfg.azure_client_id,
        client_secret=cfg.azure_client_secret,
    )


def _normalise(rec: Any) -> dict[str, Any]:
    """Convert an SDK ResourceRecommendationBase object to a plain dict."""
    props = getattr(rec, "properties", None) or rec
    # The generic savingsAmount property does not attest to a monthly period.
    ext = getattr(props, "extended_properties", {}) or {}
    evidence = provider_savings(ext.get("savingsAmount"), ext.get("savingsCurrency"))

    short_desc = getattr(props, "short_description", None)
    problem = getattr(short_desc, "problem", None) if short_desc else None
    solution = getattr(short_desc, "solution", None) if short_desc else None

    return {
        "id": rec.id,
        "name": rec.name,
        "category": getattr(props, "category", None),
        "impact": getattr(props, "impact", None),
        "impacted_field": getattr(props, "impacted_field", None),
        "impacted_value": getattr(props, "impacted_value", None),
        "problem": problem,
        "solution": solution,
        "estimated_monthly_savings": None,
        "savings_currency": None,
        "provider_savings": evidence,
        "recommendation_type_id": getattr(props, "recommendation_type_id", None),
        "last_updated": str(getattr(props, "last_updated", "")),
        "resource_metadata": {
            "resource_id": getattr(getattr(props, "resource_metadata", None), "resource_id", None),
        },
    }


class AdvisorService:
    """
    Retrieves Azure Advisor recommendations, with a focus on cost category.
    """

    def __init__(self) -> None:
        cfg = get_settings()
        self._client = AdvisorManagementClient(
            credential=_build_credential(),
            subscription_id=cfg.azure_subscription_id,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _list_recommendations(self, filter_expr: str | None = None) -> list[dict[str, Any]]:
        try:
            recs = self._client.recommendations.list(filter=filter_expr)
            return [_normalise(r) for r in recs]
        except HttpResponseError as exc:
            log.error("Advisor API error: %s", exc.message)
            raise

    def get_cost_recommendations(
        self,
        resource_group: str | None = None,
    ) -> dict[str, Any]:
        """
        Return all Advisor recommendations in the Cost category,
        optionally scoped to a resource group.

        Returns recommendations ordered by impact, not incomparable monetary estimates.
        """
        filter_expr = f"Category eq '{COST_CATEGORY}'"
        if resource_group:
            filter_expr += f" and ResourceGroup eq '{resource_group}'"

        recs = self._list_recommendations(filter_expr)

        recs.sort(key=lambda r: (-IMPACT_SCORE.get(r.get("impact"), 0), r.get("id") or ""))

        return {
            "scope": f"resourceGroup={resource_group}" if resource_group else "subscription",
            "category": COST_CATEGORY,
            "total_recommendations": len(recs),
            "savings_evidence_summary": savings_evidence_summary(recs),
            "recommendations": recs,
        }

    def get_all_recommendations(
        self,
        categories: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return recommendations across multiple categories."""
        wanted = categories or [COST_CATEGORY]
        all_recs: list[dict[str, Any]] = []

        for cat in wanted:
            filter_expr = f"Category eq '{cat}'"
            all_recs.extend(self._list_recommendations(filter_expr))

        return {
            "categories": wanted,
            "total_recommendations": len(all_recs),
            "recommendations": all_recs,
        }

    def refresh_recommendations(self) -> str:
        """
        Trigger Advisor to generate fresh recommendations.
        This is async — the new data is typically available within minutes.
        """
        cfg = get_settings()
        try:
            self._client.recommendations.generate()
            return "Recommendation generation triggered successfully."
        except HttpResponseError as exc:
            log.warning("Could not trigger Advisor refresh: %s", exc.message)
            return f"Could not trigger refresh: {exc.message}"
