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
from azure.mgmt.advisor import AdvisorManagementClient
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import get_settings
from ..config.identity import build_credential
from ..financial_evidence import provider_savings, savings_evidence_summary

log = logging.getLogger(__name__)

# Advisor categories we care about.  Others: "HighAvailability", "Security",
# "OperationalExcellence", "Performance"
COST_CATEGORY = "Cost"
ALL_CATEGORIES = [COST_CATEGORY, "HighAvailability", "Security", "OperationalExcellence", "Performance"]

IMPACT_SCORE = {"High": 3, "Medium": 2, "Low": 1}


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

    def __init__(self, *, client=None, settings=None, credential=None) -> None:
        cfg = settings if settings is not None else get_settings()
        self._owned_credential = None
        if client is not None:
            if credential is not None:
                raise ValueError("Inject a client or a credential, not both.")
            self._client = client
            self._owns_client = False
        else:
            self._owns_client = True
            if credential is None:
                credential = self._owned_credential = build_credential(cfg)
            try:
                self._client = AdvisorManagementClient(credential=credential, subscription_id=cfg.azure_subscription_id)
            except Exception:
                if self._owned_credential is not None:
                    self._owned_credential.close()
                raise

    def close(self):
        try:
            if self._owns_client:
                self._client.close()
        finally:
            if self._owned_credential is not None:
                self._owned_credential.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception_type(HttpResponseError), reraise=True)
    def _list_recommendations(self, filter_expr: str | None = None) -> list[dict[str, Any]]:
        try:
            recs = self._client.recommendations.list(filter=filter_expr)
            return [_normalise(r) for r in recs]
        except HttpResponseError as exc:
            log.warning("Advisor query failed (HTTP %s)", exc.status_code)
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
            # Azure resource-group names cannot contain single quotes.
            import re
            if not re.fullmatch(r"[\w.()-]{1,90}", resource_group) or resource_group.endswith("."):
                raise ValueError("Invalid resource group name.")
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
