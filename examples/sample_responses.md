# Sample Agent Responses

These are representative responses demonstrating the quality and format
of output you can expect from the agent.  Figures are illustrative.

---

## Query 1 — "Where am I overspending this month?"

**User:** Where am I overspending this month? Give me a breakdown by service.

**Agent:**

Based on your Azure subscription data for the **last 30 days**, here is your spending breakdown:

---

**Total spend (last 30 days): $4,217.43 USD**

| Service | Spend | % of Total |
|---|---|---|
| Virtual Machines | $1,890.12 | 44.8% |
| Azure SQL Database | $712.50 | 16.9% |
| Azure Kubernetes Service | $538.20 | 12.8% |
| Storage Accounts | $310.80 | 7.4% |
| Azure App Service | $218.40 | 5.2% |
| Other | $547.41 | 13.0% |

**Observations:**

- **Virtual Machines** represent nearly half your total spend. I found 3 deallocated VMs
  (`dev-vm-01`, `dev-vm-02`, `test-runner-03`) that are still incurring disk charges.
  Deleting or deallocating these could save approximately **$120–180/month**.

- **Azure SQL Database**: Spend is elevated. Azure Advisor flags two databases
  (`reporting-db` and `analytics-db`) as candidates for rightsizing from
  General Purpose 8 vCores → 4 vCores, saving an estimated **$340/month**.

- **AKS**: Running 3-node cluster 24/7 including weekends. Enabling the cluster
  auto-scaler and scheduling scale-to-zero for the dev cluster on weekends could
  reduce this by **20–30%** (~$108–161/month).

**Highest-impact quick win:** Rightsize `reporting-db` and `analytics-db` — low risk,
medium effort, ~$340/month savings.

---

## Query 2 — "Top 5 cost optimisation opportunities in my production subscription"

**User:** Give me the top 5 cost optimisation opportunities in my subscription,
including estimated monthly savings and effort for each.

**Agent:**

Here are your **top 5 prioritised cost optimisation opportunities**, based on Azure
Advisor recommendations and cost analysis for the **last 30 days**:

---

### Priority 1 — Rightsize Azure SQL Databases
- **Estimated Monthly Savings**: $340.00 USD
- **Effort**: Medium
- **Risk**: Low
- **What to do**:
  1. Navigate to Azure Portal → SQL Databases → `reporting-db`
  2. Under "Compute + storage", change tier from General Purpose 8 vCores → 4 vCores
  3. Repeat for `analytics-db`
  4. Monitor DTU/CPU utilisation over 7 days to confirm stability
- **Trade-offs**: Monitor query performance after downsize; peak loads may need validation.

---

### Priority 2 — Purchase Reserved Instances for Production VMs
- **Estimated Monthly Savings**: $285.00 USD
- **Effort**: Low
- **Risk**: Low
- **What to do**:
  1. In Azure Portal → Reservations, purchase 1-year reserved instances for
     `prod-web-01`, `prod-web-02`, `prod-api-01` (all Standard_D4s_v3)
  2. Estimated saving: ~38% vs. pay-as-you-go pricing
- **Trade-offs**: Reserved Instances require a 1- or 3-year commitment.
  Verify you won't need to change VM SKU within that window.

---

### Priority 3 — Delete Idle Dev/Test VMs
- **Estimated Monthly Savings**: $156.00 USD
- **Effort**: Low
- **Risk**: Low ✅ Quick Win
- **What to do**:
  1. Verify `dev-vm-01`, `dev-vm-02`, `test-runner-03` are no longer needed
  2. Take a snapshot of each disk as a precaution
  3. Delete the VMs and their associated disks
- **Trade-offs**: Verify with the owning team before deletion.

---

### Priority 4 — Remove Unattached Managed Disks
- **Estimated Monthly Savings**: $47.60 USD
- **Effort**: Low
- **Risk**: Low ✅ Quick Win
- **What to do**:
  1. In Azure Portal → Disks, filter for "Unattached"
  2. 4 unattached disks found (total: 1,190 GB)
  3. Snapshot and delete disks: `old-backup-disk`, `temp-data-01`, `legacy-disk-02`, `scratch-01`
- **Trade-offs**: Take snapshots before deletion.

---

### Priority 5 — Enable AKS Cluster Autoscaler
- **Estimated Monthly Savings**: $108.00 USD
- **Effort**: Medium
- **Risk**: Medium
- **What to do**:
  1. Run: `az aks update -n dev-cluster -g myRG --enable-cluster-autoscaler --min-count 1 --max-count 5`
  2. Configure a scheduled scale-to-zero on weekends for the `dev-cluster`
  3. Consider spot node pools for batch workloads
- **Trade-offs**: Ensure your workloads tolerate node-level interruptions.
  Test autoscaler in dev before enabling in production.

---

### Summary

| | |
|---|---|
| **Total potential monthly savings** | **$936.60 USD** |
| **Annualised** | **$11,239 USD** |
| **Quick wins (low effort/risk)** | 3 recommendations |
| **Data covers** | Last 30 days |

**Highest impact quick win:** Delete idle dev/test VMs — can be done today,
saving $156/month with zero performance risk.

---

## Query 3 — "Show me idle or underutilised resources in West Europe"

**User:** Show me idle or underutilised resources I should clean up.
Focus on quick wins with low risk.

**Agent:**

I scanned your subscription for idle and underutilised resources.
Here is what I found, sorted by ease of cleanup:

---

### Quick Wins (Low Effort, Low Risk)

#### Unattached Managed Disks (4 found)

| Disk Name | Resource Group | Size | SKU | Est. Monthly Cost |
|---|---|---|---|---|
| `old-backup-disk` | `rg-legacy` | 512 GB | Standard HDD | $20.48 |
| `temp-data-01` | `rg-dev` | 256 GB | Premium SSD | $35.33 |
| `legacy-disk-02` | `rg-archive` | 128 GB | Standard SSD | $10.24 |
| `scratch-01` | `rg-dev` | 294 GB | Standard HDD | $11.76 |

**Action:** Snapshot each disk, then delete. Saves **~$77.81/month**.

```bash
# Example: snapshot then delete a disk
az snapshot create -g rg-legacy -n old-backup-disk-snapshot \
  --source old-backup-disk

az disk delete -g rg-legacy -n old-backup-disk --yes
```

---

#### Unattached Public IP Addresses (2 found)

| Name | Resource Group | SKU |
|---|---|---|
| `pip-test-001` | `rg-dev` | Standard |
| `pip-old-lb` | `rg-networking` | Standard |

**Action:** Delete both IPs. Saves **~$7.20/month**.

```bash
az network public-ip delete -g rg-dev -n pip-test-001
az network public-ip delete -g rg-networking -n pip-old-lb
```

---

### Moderate Effort

#### Deallocated VMs (3 found)

| VM Name | Resource Group | SKU | Power State |
|---|---|---|---|
| `dev-vm-01` | `rg-dev` | Standard_D4s_v3 | Deallocated |
| `dev-vm-02` | `rg-dev` | Standard_D4s_v3 | Deallocated |
| `test-runner-03` | `rg-test` | Standard_B4ms | Stopped |

These VMs are not running but their **managed disks continue to incur charges**.
**Action:** Confirm with owning team, then delete. Saves **~$120–180/month**.

---

### Summary

| Resource Type | Count | Est. Monthly Savings |
|---|---|---|
| Unattached Disks | 4 | $77.81 |
| Orphaned Public IPs | 2 | $7.20 |
| Deallocated VMs | 3 | ~$150.00 |
| **Total** | **9** | **~$235.01** |

**Start here:** Unattached disks and public IPs are risk-free to clean up and
can be done in under 30 minutes. That alone saves ~$85/month with zero impact
on running workloads.
