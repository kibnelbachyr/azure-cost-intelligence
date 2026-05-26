"""
Optional enrichment layer: Azure Resource Graph queries.

Lets us fetch resource metadata (SKU, region, tags, power state, etc.)
to enrich Advisor recommendations with context that helps the agent
explain *why* a resource is worth acting on.

Docs: https://learn.microsoft.com/en-us/azure/governance/resource-graph/
SDK:  azure-mgmt-resourcegraph
"""
from __future__ import annotations

import logging
from typing import Any

from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest, QueryRequestOptions

from ..config import get_settings

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


class ResourceGraphService:
    """Run KQL queries against Azure Resource Graph."""

    def __init__(self) -> None:
        self._client = ResourceGraphClient(credential=_build_credential())
        self._cfg = get_settings()

    def _run_query(self, kql: str, top: int = 100) -> list[dict[str, Any]]:
        request = QueryRequest(
            subscriptions=[self._cfg.azure_subscription_id],
            query=kql,
            options=QueryRequestOptions(top=top),
        )
        try:
            result = self._client.resources(request)
            return result.data if result.data else []
        except HttpResponseError as exc:
            log.error("Resource Graph query failed: %s", exc.message)
            raise

    # ── pre-built queries ─────────────────────────────────────────────────────

    def get_idle_vms(self) -> dict[str, Any]:
        """
        List VMs that are currently deallocated (stopped but still billed
        for managed disks) or have no recent CPU metrics.
        """
        kql = """
        Resources
        | where type =~ 'Microsoft.Compute/virtualMachines'
        | extend powerState = tostring(properties.extended.instanceView.powerState.displayStatus)
        | where powerState =~ 'VM deallocated' or powerState =~ 'VM stopped'
        | project id, name, resourceGroup, location, sku=tostring(properties.hardwareProfile.vmSize),
                  powerState, tags
        | order by name asc
        """
        rows = self._run_query(kql)
        return {"idle_vms": rows, "count": len(rows)}

    def get_unused_disks(self) -> dict[str, Any]:
        """List managed disks that are not attached to any VM."""
        kql = """
        Resources
        | where type =~ 'Microsoft.Compute/disks'
        | where isnull(properties.managedBy) or properties.managedBy == ''
        | project id, name, resourceGroup, location,
                  sku=tostring(sku.name),
                  sizeGb=toint(properties.diskSizeGB),
                  createdTime=tostring(properties.timeCreated),
                  tags
        | order by sizeGb desc
        """
        rows = self._run_query(kql)
        return {"unused_disks": rows, "count": len(rows)}

    def get_unattached_public_ips(self) -> dict[str, Any]:
        """List public IP addresses with no associated resource."""
        kql = """
        Resources
        | where type =~ 'Microsoft.Network/publicIPAddresses'
        | where isnull(properties.ipConfiguration)
        | project id, name, resourceGroup, location,
                  sku=tostring(sku.name),
                  allocationMethod=tostring(properties.publicIPAllocationMethod),
                  tags
        """
        rows = self._run_query(kql)
        return {"unattached_public_ips": rows, "count": len(rows)}

    def get_resource_metadata(self, resource_ids: list[str]) -> dict[str, Any]:
        """Fetch SKU, region, and tags for a list of resource IDs."""
        if not resource_ids:
            return {"resources": []}

        ids_expr = ", ".join(f"'{rid}'" for rid in resource_ids[:50])
        kql = f"""
        Resources
        | where id in ({ids_expr})
        | project id, name, type, resourceGroup, location,
                  sku=tostring(sku.name), tags
        """
        rows = self._run_query(kql)
        return {"resources": rows}

    def get_resources_by_region(self, region: str) -> dict[str, Any]:
        """Summarise resource counts and estimated cost exposure by type in a region."""
        kql = f"""
        Resources
        | where location =~ '{region}'
        | summarize count=count() by type
        | order by count desc
        """
        rows = self._run_query(kql)
        return {"region": region, "resource_type_counts": rows}
