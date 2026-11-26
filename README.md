# Azure Cost Optimization Agent

> Experimental MVP. Recommendations are advisory, not authorization to change or delete resources. Risk labels are heuristic; monetary estimates require explicit source, period and currency evidence and are not validated financial assessments. Confirm ownership, dependencies, recovery, actual prices and explicit human approval before acting. No production or live-model assurance is claimed.

## Offline regression checks

With Python 3.11, run `python -m unittest discover -s tests -v` from the repository root. These tests exercise the deterministic recommendation engine using fictional inputs; no Azure credentials, dependency installation or cloud calls are required. The CI workflow runs these checks only, not deployments. Full SDK compatibility, live provider data and model output remain unverified.

See [management SDK contract suite](docs/sdk-contracts.md) for synthetic provider responses and the tested compatibility boundary. The old Foundry runner needs a separate migration; do not attempt live operation based on the management SDK checks.

See [financial evidence contract](docs/financial-evidence.md) for the offline ranking, currency, unknown-savings and scope rules. The current Advisor adapter retains generic provider savings with unknown period; it does not infer monthly savings. No aggregate potential savings is reported.

An MVP AI agent built on **Azure AI Foundry** that analyses your Azure subscription
costs and surfaces concrete, prioritised optimisation recommendations in plain English.

Ask it questions like:
- *"Where am I overspending this month?"*
- *"Give me the top 5 cost optimisation opportunities in my production subscription."*
- *"Show me idle or underutilised resources I should clean up."*

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Repository Structure](#3-repository-structure)
4. [Prerequisites](#4-prerequisites)
5. [Deployment Steps](#5-deployment-steps)
6. [Configuration Reference](#6-configuration-reference)
7. [Running the Agent](#7-running-the-agent)
8. [Example Queries & Responses](#8-example-queries--responses)
9. [Operations & Monitoring](#9-operations--monitoring)
10. [Security Notes](#10-security-notes)
11. [Future Enhancements](#11-future-enhancements)

---

## 1. Overview

### What it does

The agent combines three data sources to produce a ranked optimisation plan:

| Source | What it provides |
|---|---|
| **Azure Cost Management** | Actual spend broken down by service, resource group, tag, or time period |
| **Azure Advisor** | Microsoft's built-in recommendations (right-sizing, Reserved Instances, idle resources, etc.) |
| **Azure Resource Graph** | Resource metadata — SKU, region, power state, and attachment status — for enrichment |

The agent runs as a conversational loop (single-turn or multi-turn) powered by
a GPT-4o model deployed inside your AI Foundry project.  It calls tools
dynamically based on the user's question, then synthesises the results into
a structured, human-readable response.

### MVP scope and limitations

**In scope:**
- Single-subscription analysis
- Cost breakdown by service, resource group, or tag
- Azure Advisor cost-category recommendations
- Idle resource detection (deallocated VMs, unattached disks, orphaned public IPs)
- Prioritised recommendation list with effort/risk classification
- Interactive CLI and single-query mode

**Out of scope for MVP (see §11 for roadmap):**
- Multi-subscription or multi-tenant analysis
- Automated remediation
- Budget alert integration
- Custom dashboards or UI
- Scheduled/recurring reports

---

## 2. Architecture

### 2.1 Logical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User (CLI)                           │
└────────────────────────────┬────────────────────────────────┘
                             │  natural-language query
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              Azure AI Foundry — Agent Runtime               │
│                                                             │
│   System Prompt: "You are Azure Cost Advisor…"              │
│   Model: GPT-4o (deployed in AI Foundry project)            │
│                                                             │
│   Registered Tools:                                         │
│   ┌──────────────────────────────────────────────────────┐  │
│   │ get_cost_summary          get_top_cost_drivers        │  │
│   │ get_cost_by_tag           get_advisor_cost_recs       │  │
│   │ correlate_cost_and_advisor get_idle_resources         │  │
│   │ get_cost_trend                                        │  │
│   └──────────────────────────────────────────────────────┘  │
└────────────┬────────────────────────────────────────────────┘
             │  tool call  (JSON arguments)
             ▼
┌─────────────────────────────────────────────────────────────┐
│                     Tool Handler Layer                      │
│              (src/tools/handlers.py)                        │
│                                                             │
│   ┌─────────────────┐  ┌──────────────────┐  ┌──────────┐  │
│   │ CostManagement  │  │  AdvisorService  │  │ Resource │  │
│   │    Service      │  │                  │  │  Graph   │  │
│   │  (Cost Mgmt     │  │ (Advisor API)    │  │ Service  │  │
│   │     API)        │  │                  │  │  (KQL)   │  │
│   └────────┬────────┘  └────────┬─────────┘  └────┬─────┘  │
│            │                   │                  │         │
│            └─────────┬─────────┘                  │         │
│                      │              ┌──────────────┘         │
│                      ▼              ▼                        │
│             ┌─────────────────────────┐                      │
│             │  Recommendation Engine  │                      │
│             │ (correlate + rank recs) │                      │
│             └─────────────────────────┘                      │
└────────────────────────────┬────────────────────────────────┘
                             │  tool result  (JSON)
                             ▼
                      [Agent reasons]
                             │
                             ▼
                    Structured response
                    (Markdown text with
                     ranked recommendations)
```

### 2.2 Azure Services Used

| Service | Purpose |
|---|---|
| **Azure AI Foundry** | Agent runtime, model deployment, tool orchestration |
| **Azure OpenAI (GPT-4o)** | Language model powering the agent |
| **Azure Cost Management + Billing** | Actual spend data, time series, cost by dimension |
| **Azure Advisor** | Microsoft-generated optimisation recommendations |
| **Azure Resource Graph** | Resource metadata queries (KQL) |
| **Azure Active Directory** | Service Principal / Managed Identity authentication |
| *(Optional) Azure Key Vault* | Secret management in production |
| *(Optional) Application Insights* | Observability |

### 2.3 Data Flow (Sequence)

```
User           CLI (main.py)      AgentRunner       AI Foundry     Tool Handlers     Azure APIs
 │                  │                  │                 │                │               │
 │ "Top 5 opts…"    │                  │                 │                │               │
 │─────────────────►│                  │                 │                │               │
 │                  │ chat(query)      │                 │                │               │
 │                  │─────────────────►│                 │                │               │
 │                  │                  │ create_message  │                │               │
 │                  │                  │────────────────►│                │               │
 │                  │                  │ create_run      │                │               │
 │                  │                  │────────────────►│                │               │
 │                  │                  │ [poll]          │                │               │
 │                  │                  │◄───────────────►│                │               │
 │                  │                  │                 │ REQUIRES_ACTION│               │
 │                  │                  │◄────────────────│ (tool call:    │               │
 │                  │                  │                 │  correlate…)   │               │
 │                  │                  │ dispatch(fn,args)│               │               │
 │                  │                  │────────────────────────────────►│               │
 │                  │                  │                 │                │ Cost API call │
 │                  │                  │                 │                │──────────────►│
 │                  │                  │                 │                │◄──────────────│
 │                  │                  │                 │                │ Advisor call  │
 │                  │                  │                 │                │──────────────►│
 │                  │                  │                 │                │◄──────────────│
 │                  │                  │                 │                │ Graph KQL     │
 │                  │                  │                 │                │──────────────►│
 │                  │                  │                 │                │◄──────────────│
 │                  │                  │◄────────────────────────────────│ JSON result   │
 │                  │                  │ submit_tool_outputs             │               │
 │                  │                  │────────────────►│                │               │
 │                  │                  │ [poll → COMPLETED]              │               │
 │                  │                  │◄────────────────│                │               │
 │                  │                  │ list_messages   │                │               │
 │                  │                  │────────────────►│                │               │
 │                  │◄─────────────────│ assistant text  │                │               │
 │◄─────────────────│ formatted output │                 │                │               │
```

### 2.4 Security & Identity

#### Authentication

The agent authenticates to all Azure APIs using either:

- **Managed Identity** (recommended for production) — set `USE_MANAGED_IDENTITY=true`.
  The identity is attached to the Azure Container App / Function / VM running the code.
  No secrets needed in configuration.
- **Service Principal** (for local development) — set `AZURE_CLIENT_ID` and
  `AZURE_CLIENT_SECRET`.  Optionally store these in Azure Key Vault and load via
  the `@Microsoft.KeyVault()` reference syntax in App Service configuration.

#### Required RBAC Roles

Assign these to the Managed Identity or Service Principal at **subscription scope**:

| Role | Why |
|---|---|
| `Reader` | List resources, access Resource Graph |
| `Cost Management Reader` | Read cost data via Cost Management API |

> Azure Advisor recommendations are accessible to any principal with `Reader` access
> on the subscription — no extra role needed.

#### Secrets storage

| Environment | Recommendation |
|---|---|
| Local dev | `.env` file (never committed — already in `.gitignore`) |
| Azure Container Apps / App Service | Environment variables via managed configuration, secrets from Key Vault |
| Production | Azure Key Vault with Managed Identity access |

---

## 3. Repository Structure

```
azure-cost-intelligence/
├── README.md                   ← This file
├── requirements.txt            ← Python dependencies
├── .env.example                ← Template — copy to .env and fill in
│
├── src/
│   ├── config/
│   │   └── settings.py         ← Pydantic Settings (env vars → typed config)
│   │
│   ├── services/
│   │   ├── cost_management.py  ← Azure Cost Management API wrapper
│   │   ├── advisor.py          ← Azure Advisor API wrapper
│   │   └── resource_graph.py   ← Azure Resource Graph KQL wrapper
│   │
│   ├── tools/
│   │   ├── definitions.py      ← JSON schemas for all agent tools
│   │   └── handlers.py         ← Tool handler implementations + dispatcher
│   │
│   ├── agent/
│   │   ├── prompts.py          ← System prompt for the agent
│   │   └── runner.py           ← Azure AI Foundry agent run loop
│   │
│   ├── recommendations/
│   │   └── engine.py           ← Correlation + ranking of recommendations
│   │
│   └── main.py                 ← CLI entry point (single query or interactive)
│
├── examples/
│   ├── run_examples.py         ← Runnable demo script (3 example queries)
│   └── sample_responses.md     ← Annotated example agent responses
│
└── scripts/
    └── setup_azure.sh          ← Azure resource provisioning script
```

---

## 4. Prerequisites

### Azure

- [ ] An **Azure subscription** with Owner or Contributor + User Access Administrator role
- [ ] **Azure AI Foundry** project created (or you'll create one in §5)
- [ ] A **GPT-4o deployment** inside your AI Foundry project (model catalog → deploy)

### Roles (on the subscription or resource group)

| Who | Role | Scope |
|---|---|---|
| Your service principal / managed identity | `Reader` | Subscription |
| Your service principal / managed identity | `Cost Management Reader` | Subscription |

### Local tools

- [ ] **Python 3.11+**
- [ ] **Azure CLI** (`az`) installed and logged in (`az login`)
- [ ] **jq** (used by the setup script)
- [ ] **pip** or a virtual environment manager

---

## 5. Deployment Steps

### Step 1 — Clone the repository

```bash
git clone https://github.com/your-org/azure-cost-intelligence.git
cd azure-cost-intelligence
```

### Step 2 — Create a Python virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3 — Provision Azure resources (automated)

> This step creates a resource group, Service Principal, assigns roles,
> and creates an AI Foundry Hub + Project.

```bash
export AZURE_SUBSCRIPTION_ID="<your-subscription-id>"
export RESOURCE_GROUP="rg-cost-agent"        # or your preferred name
export LOCATION="eastus"

chmod +x scripts/setup_azure.sh
./scripts/setup_azure.sh
```

The script writes a `.env` file with the credentials.  
**After it completes, you must manually do one thing:**

### Step 4 — Add the AI Foundry connection string

1. Open [Azure AI Foundry Portal](https://ai.azure.com)
2. Navigate to your project → **Overview**
3. Under **"Get started in SDK"**, copy the connection string
   (format: `<region>.api.azureml.ms;<sub>;<rg>;<project>`)
4. Paste it into `.env`:

```bash
AZURE_AI_PROJECT_CONNECTION_STRING=eastus.api.azureml.ms;xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx;rg-cost-agent;cost-optimization-agent
```

### Step 5 — Deploy a GPT-4o model in AI Foundry

1. In the AI Foundry Portal → your project → **Model catalog**
2. Search for `gpt-4o` and click **Deploy**
3. Choose deployment name (default: `gpt-4o`) — this must match
   `AZURE_OPENAI_DEPLOYMENT_NAME` in your `.env`

### Step 6 — Validate the configuration

```bash
python -c "
from dotenv import load_dotenv; load_dotenv()
from src.config import get_settings
s = get_settings()
print('Tenant:', s.azure_tenant_id)
print('Subscription:', s.azure_subscription_id)
print('AI Foundry:', s.azure_ai_project_connection_string[:40], '...')
print('Model:', s.azure_openai_deployment_name)
print('OK')
"
```

### Step 7 — Run the agent

```bash
# Interactive mode
python -m src.main --interactive

# Single query
python -m src.main "Where am I overspending this month?"

# Run all example queries
python examples/run_examples.py
```

### Step 8 — (Optional) Deploy to Azure Container Apps

For a persistent, scalable deployment:

```bash
# Build and push a container image
az acr create --name costAgentRegistry --resource-group rg-cost-agent \
  --sku Basic --admin-enabled true

az acr build --registry costAgentRegistry \
  --image cost-agent:latest .

# Create a Container App (add env vars via --env-vars or Key Vault refs)
az containerapp create \
  --name cost-agent \
  --resource-group rg-cost-agent \
  --environment cost-agent-env \
  --image costAgentRegistry.azurecr.io/cost-agent:latest \
  --target-port 8080 \
  --env-vars \
    AZURE_TENANT_ID=<tenant-id> \
    AZURE_SUBSCRIPTION_ID=<sub-id> \
    USE_MANAGED_IDENTITY=true \
    AZURE_AI_PROJECT_CONNECTION_STRING=<conn-str> \
    AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

---

## 6. Configuration Reference

All values are loaded from environment variables (or a `.env` file in the project root).

| Variable | Required | Default | Description |
|---|---|---|---|
| `AZURE_TENANT_ID` | ✅ | — | Azure Active Directory tenant ID |
| `AZURE_SUBSCRIPTION_ID` | ✅ | — | Target subscription for cost analysis |
| `AZURE_CLIENT_ID` | ✅* | — | Service Principal app ID (* not needed with Managed Identity) |
| `AZURE_CLIENT_SECRET` | ✅* | — | Service Principal secret (* not needed with Managed Identity) |
| `USE_MANAGED_IDENTITY` | | `false` | Set `true` when running inside Azure |
| `AZURE_AI_PROJECT_CONNECTION_STRING` | ✅ | — | AI Foundry project SDK connection string |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | | `gpt-4o` | Model deployment name in AI Foundry |
| `DEFAULT_COST_LOOKBACK_DAYS` | | `30` | Default time window for cost queries (1–365) |
| `TOP_COST_DRIVERS_LIMIT` | | `10` | Number of top cost drivers to return |

---

## 7. Running the Agent

### Interactive mode (multi-turn conversation)

```bash
python -m src.main --interactive
```

The agent remembers the conversation thread, so follow-up questions work:

```
You: Where am I overspending?
Agent: [detailed breakdown]

You: Focus on the Virtual Machines spend — how can I reduce it?
Agent: [targeted VM recommendations]
```

### Single-query mode

```bash
python -m src.main "Top 5 cost optimisation opportunities"
```

### Run all examples

```bash
python examples/run_examples.py
```

### Programmatic usage

```python
from dotenv import load_dotenv
load_dotenv()

from src.agent.runner import AgentRunner

runner = AgentRunner()
thread = runner.create_thread()

# First query
response = runner.chat(
    "Where am I overspending this month?",
    thread_id=thread.id,
)
print(response)

# Follow-up (same thread = same context)
response = runner.chat(
    "What are the quick wins I can implement this week?",
    thread_id=thread.id,
)
print(response)
```

---

## 8. Example Queries & Responses

See [`examples/sample_responses.md`](examples/sample_responses.md) for full annotated
examples with illustrative figures.

### Suggested queries

| Goal | Query |
|---|---|
| Monthly overview | `"Where am I overspending this month? Give me a breakdown by service."` |
| Top opportunities | `"Give me the top 5 cost optimisation opportunities with estimated savings."` |
| Idle resources | `"Show me idle or underutilised resources I should clean up."` |
| Cost trends | `"Show me my cost trend for the last 90 days — are we spending more?"` |
| Tag-based | `"How much did the Production environment cost last month?"` |
| RG-specific | `"What are the optimisation opportunities in resource group rg-analytics?"` |
| Quick wins | `"What are the lowest-effort, lowest-risk things I can do today to reduce my bill?"` |

---

## 9. Operations & Monitoring

### Logging

The application uses Python's standard `logging` module.  Set the log level via:

```bash
export LOG_LEVEL=DEBUG   # DEBUG | INFO | WARNING | ERROR
```

Key log events:
- `INFO` — Agent initialised, tool calls dispatched, run completed
- `WARNING` — Advisor refresh failures, non-critical API issues
- `ERROR` — API call failures, configuration errors

### API Rate Limits

| API | Default Limit | Notes |
|---|---|---|
| Cost Management | 30 req/min per subscription | Retry logic (3 attempts, exponential backoff) is built in |
| Azure Advisor | ~200 req/hour | Recommendations are cached by Advisor — refresh is async |
| Resource Graph | 15 req/5 sec (per tenant) | Each `get_idle_resources` call sends 3 KQL queries |
| Azure OpenAI | Depends on deployment quota | Monitor token usage in AI Foundry portal |

### Recommended monitoring additions

1. **Application Insights**: Wrap the `AgentRunner.chat()` method with custom telemetry:

```python
from azure.monitor.opentelemetry import configure_azure_monitor
configure_azure_monitor(connection_string="InstrumentationKey=...")
```

2. **Azure Monitor Alerts**: Create alerts on:
   - Cost anomaly detection (Cost Management → Alerts)
   - Budget threshold breaches
   - HTTP 429 errors from the tool layer

3. **Log Analytics**: Stream container logs to a Log Analytics workspace for
   long-term retention and dashboarding.

---

## 10. Security Notes

1. **Never commit `.env`** — it is already in `.gitignore`, but double-check.
2. **Prefer Managed Identity** in production to eliminate long-lived secrets.
3. **Least-privilege**: The agent only needs `Reader` + `Cost Management Reader`.
   Do not grant `Contributor` or higher.
4. **Key Vault for secrets**: In production, reference secrets via
   `@Microsoft.KeyVault(SecretUri=...)` in App Service / Container App configuration.
5. **Network isolation**: For high-security environments, deploy the tool layer
   inside a VNet and use Private Endpoints for Cost Management / Advisor access
   (via Azure Resource Manager private endpoint).

---

## 11. Future Enhancements

| Enhancement | Description | Effort |
|---|---|---|
| **Multi-subscription support** | Accept a list of subscription IDs; aggregate and compare costs across subs | Medium |
| **Multi-tenant support** | Support cross-tenant analysis for MSPs and enterprise EA enrollments | High |
| **Budget integration** | Read Azure Budgets and alert when spend approaches a budget threshold | Low |
| **Automated remediation** | With approval workflow, execute low-risk actions (delete unattached disks, stop VMs) | High |
| **Ticket creation** | Auto-create Azure DevOps / Jira work items for each accepted recommendation | Medium |
| **Scheduled reports** | Run the agent on a schedule and email/Teams-message the weekly optimisation report | Medium |
| **Web UI** | Expose the agent via Azure Static Web Apps + Azure Functions (HTTP trigger) | Medium |
| **Reserved Instance advisor** | Deep RI/Savings Plan analysis using Azure Commerce APIs | High |
| **Custom policies** | Allow teams to mark certain resources as "exempt" from recommendations | Low |
| **Forecast-aware advice** | Use Cost Management forecasts to warn about projected overspend | Medium |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-improvement`
3. Commit with descriptive messages
4. Open a pull request

---

## License

MIT — see `LICENSE` file.
