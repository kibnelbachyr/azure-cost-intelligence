"""
Thin wrapper around the Azure Cost Management REST API.

Docs: https://learn.microsoft.com/en-us/azure/cost-management-billing/
SDK:  azure-mgmt-costmanagement
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    QueryDefinition,
    QueryDataset,
    QueryTimePeriod,
    QueryAggregation,
    QueryGrouping,
    GranularityType,
)
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import get_settings
from ..financial_evidence import validated_cost_rows

log = logging.getLogger(__name__)


def _build_credential():
    cfg = get_settings()
    if cfg.use_managed_identity:
        return DefaultAzureCredential()
    return ClientSecretCredential(
        tenant_id=cfg.azure_tenant_id,
        client_id=cfg.azure_client_id,
        client_secret=cfg.azure_client_secret,
    )


def _subscription_scope(subscription_id: str) -> str:
    return f"subscriptions/{subscription_id}"


def _rg_scope(subscription_id: str, resource_group: str) -> str:
    return f"subscriptions/{subscription_id}/resourceGroups/{resource_group}"


class CostManagementService:
    """
    Queries Azure Cost Management for actual-spend data.

    Preserve a single explicit provider currency; reject missing/mixed currency.
    """

    def __init__(self) -> None:
        self._client = CostManagementClient(credential=_build_credential())
        self._cfg = get_settings()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _date_range(self, lookback_days: int) -> tuple[str, str]:
        """Return (from_date, to_date) strings in YYYY-MM-DD format."""
        now = datetime.now(tz=timezone.utc)
        start = now - timedelta(days=lookback_days)
        return start.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _query(self, scope: str, definition: QueryDefinition) -> list[dict[str, Any]]:
        try:
            result = self._client.query.usage(scope=scope, parameters=definition)
        except HttpResponseError as exc:
            log.error("Cost Management query failed for scope %s: %s", scope, exc.message)
            raise

        # Do not silently report a partial page as total actual spend.
        if getattr(result, "next_link", None):
            raise ValueError("Paginated cost result requires explicit pagination support.")
        if not result.rows:
            return []

        columns = [c.name for c in result.columns]
        return [dict(zip(columns, row)) for row in result.rows]

    # ── public API ────────────────────────────────────────────────────────────

    def get_cost_summary(
        self,
        subscription_id: str | None = None,
        resource_group: str | None = None,
        lookback_days: int | None = None,
        granularity: str = "Monthly",
    ) -> dict[str, Any]:
        """
        Return total cost and a time-series breakdown for the given scope.

        Args:
            subscription_id: Defaults to the subscription in settings.
            resource_group:  If set, scope is narrowed to this RG.
            lookback_days:   Defaults to settings.default_cost_lookback_days.
            granularity:     "Daily" | "Monthly" | "None"
        """
        cfg = self._cfg
        sub_id = subscription_id or cfg.azure_subscription_id
        days = lookback_days or cfg.default_cost_lookback_days
        from_date, to_date = self._date_range(days)

        scope = _rg_scope(sub_id, resource_group) if resource_group else _subscription_scope(sub_id)

        gran = GranularityType.MONTHLY if granularity == "Monthly" else GranularityType.DAILY

        definition = QueryDefinition(
            type="ActualCost",
            timeframe="Custom",
            time_period=QueryTimePeriod(from_property=from_date, to=to_date),
            dataset=QueryDataset(
                granularity=gran,
                aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
            ),
        )

        rows = self._query(scope, definition)
        total, currency, amounts = validated_cost_rows(rows)

        return {
            "scope": scope,
            "from_date": from_date,
            "to_date": to_date,
            "total_cost": float(total) if total is not None else None,
            "currency": currency,
            "granularity": granularity,
            "time_series": rows,
        }

    def get_top_cost_drivers(
        self,
        subscription_id: str | None = None,
        resource_group: str | None = None,
        lookback_days: int | None = None,
        group_by: str = "ServiceName",
        limit: int | None = None,
    ) -> dict[str, Any]:
        """
        Return the top cost drivers grouped by the given dimension.

        Args:
            group_by: "ServiceName" | "ResourceGroupName" | "ResourceId" | "MeterCategory"
        """
        cfg = self._cfg
        sub_id = subscription_id or cfg.azure_subscription_id
        days = lookback_days or cfg.default_cost_lookback_days
        top_n = limit or cfg.top_cost_drivers_limit
        from_date, to_date = self._date_range(days)

        scope = _rg_scope(sub_id, resource_group) if resource_group else _subscription_scope(sub_id)

        definition = QueryDefinition(
            type="ActualCost",
            timeframe="Custom",
            time_period=QueryTimePeriod(from_property=from_date, to=to_date),
            dataset=QueryDataset(
                granularity=GranularityType.NONE,
                aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
                grouping=[QueryGrouping(type="Dimension", name=group_by)],
            ),
        )

        rows = self._query(scope, definition)
        total, currency, amounts = validated_cost_rows(rows)
        rows_sorted = sorted(zip(rows, amounts), key=lambda item: item[1], reverse=True)[:top_n]

        drivers = [
            {
                "name": r.get(group_by, "Unknown"),
                "cost": float(amount),
                "percentage": round(float(amount / total * 100), 1) if total is not None and total > 0 else None,
            }
            for r, amount in rows_sorted
        ]

        return {
            "scope": scope,
            "from_date": from_date,
            "to_date": to_date,
            "group_by": group_by,
            "total_cost": float(total) if total is not None else None,
            "currency": currency,
            "top_drivers": drivers,
        }

    def get_cost_by_tag(
        self,
        tag_name: str,
        tag_value: str,
        subscription_id: str | None = None,
        lookback_days: int | None = None,
    ) -> dict[str, Any]:
        """Return total cost for resources carrying a specific tag key=value pair."""
        cfg = self._cfg
        sub_id = subscription_id or cfg.azure_subscription_id
        days = lookback_days or cfg.default_cost_lookback_days
        from_date, to_date = self._date_range(days)
        scope = _subscription_scope(sub_id)

        from azure.mgmt.costmanagement.models import QueryFilter, QueryComparisonExpression

        definition = QueryDefinition(
            type="ActualCost",
            timeframe="Custom",
            time_period=QueryTimePeriod(from_property=from_date, to=to_date),
            dataset=QueryDataset(
                granularity=GranularityType.NONE,
                aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
                filter=QueryFilter(
                    tags=QueryComparisonExpression(
                        name=tag_name,
                        operator="In",
                        values=[tag_value],
                    )
                ),
            ),
        )

        rows = self._query(scope, definition)
        total, currency, amounts = validated_cost_rows(rows)

        return {
            "scope": scope,
            "tag": f"{tag_name}={tag_value}",
            "from_date": from_date,
            "to_date": to_date,
            "total_cost": float(total) if total is not None else None,
            "currency": currency,
        }

    def get_cost_trend(
        self,
        subscription_id: str | None = None,
        lookback_days: int = 90,
    ) -> dict[str, Any]:
        """Return daily costs for the last N days to reveal spend trends."""
        return self.get_cost_summary(
            subscription_id=subscription_id,
            lookback_days=lookback_days,
            granularity="Daily",
        )
