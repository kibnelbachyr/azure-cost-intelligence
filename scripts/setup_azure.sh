#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Azure resource provisioning script for the Cost Optimization Agent MVP.
#
# Prerequisites:
#   - Azure CLI installed and logged in  (az login)
#   - jq installed
#   - Variables below set to your values
#
# Usage:
#   chmod +x scripts/setup_azure.sh
#   ./scripts/setup_azure.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-}"
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-cost-agent}"
LOCATION="${LOCATION:-eastus}"
AI_FOUNDRY_HUB_NAME="${AI_FOUNDRY_HUB_NAME:-hub-cost-agent}"
AI_FOUNDRY_PROJECT_NAME="${AI_FOUNDRY_PROJECT_NAME:-cost-optimization-agent}"
SP_NAME="${SP_NAME:-sp-cost-agent}"

if [[ -z "$SUBSCRIPTION_ID" ]]; then
  echo "ERROR: Set AZURE_SUBSCRIPTION_ID before running this script."
  exit 1
fi

echo "──────────────────────────────────────────────────"
echo " Azure Cost Optimization Agent — Resource Setup"
echo "──────────────────────────────────────────────────"
echo "Subscription : $SUBSCRIPTION_ID"
echo "Resource Group: $RESOURCE_GROUP"
echo "Location      : $LOCATION"
echo ""

# ── 1. Set active subscription ────────────────────────────────────────────────
echo "[1/7] Setting active subscription..."
az account set --subscription "$SUBSCRIPTION_ID"

# ── 2. Create resource group ──────────────────────────────────────────────────
echo "[2/7] Creating resource group '$RESOURCE_GROUP'..."
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output table

# ── 3. Create Service Principal ───────────────────────────────────────────────
echo "[3/7] Creating Service Principal '$SP_NAME'..."
SP_JSON=$(az ad sp create-for-rbac \
  --name "$SP_NAME" \
  --role "Reader" \
  --scopes "/subscriptions/$SUBSCRIPTION_ID" \
  --output json)

CLIENT_ID=$(echo "$SP_JSON" | jq -r '.appId')
CLIENT_SECRET=$(echo "$SP_JSON" | jq -r '.password')
TENANT_ID=$(echo "$SP_JSON" | jq -r '.tenant')

echo "  Client ID  : $CLIENT_ID"
echo "  Tenant ID  : $TENANT_ID"
echo "  (secret printed to .env only)"

# ── 4. Assign Cost Management Reader role ─────────────────────────────────────
echo "[4/7] Assigning 'Cost Management Reader' role..."
az role assignment create \
  --assignee "$CLIENT_ID" \
  --role "Cost Management Reader" \
  --scope "/subscriptions/$SUBSCRIPTION_ID" \
  --output table

# Azure Advisor is accessible via the Reader role already assigned above.

# ── 5. Create AI Foundry Hub + Project ───────────────────────────────────────
echo "[5/7] Creating AI Foundry Hub '$AI_FOUNDRY_HUB_NAME'..."
az ml workspace create \
  --name "$AI_FOUNDRY_HUB_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --kind hub \
  --output table 2>/dev/null || echo "  (Hub may already exist — continuing)"

echo "  Creating AI Foundry Project '$AI_FOUNDRY_PROJECT_NAME'..."
az ml workspace create \
  --name "$AI_FOUNDRY_PROJECT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --kind project \
  --hub-id "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.MachineLearningServices/workspaces/$AI_FOUNDRY_HUB_NAME" \
  --output table 2>/dev/null || echo "  (Project may already exist — continuing)"

# ── 6. Retrieve connection string ─────────────────────────────────────────────
echo "[6/7] Retrieving AI Foundry connection string..."
CONNECTION_STRING=$(az ml workspace show \
  --name "$AI_FOUNDRY_PROJECT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "discovery_url" \
  --output tsv 2>/dev/null || echo "MANUAL_LOOKUP_REQUIRED")

echo "  Connection string hint: $CONNECTION_STRING"
echo "  → Get the full SDK connection string from AI Foundry Portal > Project > Overview > SDK"

# ── 7. Write .env file ────────────────────────────────────────────────────────
echo "[7/7] Writing .env file..."
cat > .env <<EOF
AZURE_TENANT_ID=${TENANT_ID}
AZURE_SUBSCRIPTION_ID=${SUBSCRIPTION_ID}
AZURE_CLIENT_ID=${CLIENT_ID}
AZURE_CLIENT_SECRET=${CLIENT_SECRET}
USE_MANAGED_IDENTITY=false

# Paste your AI Foundry project connection string here (from Portal):
AZURE_AI_PROJECT_CONNECTION_STRING=REPLACE_ME

AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
DEFAULT_COST_LOOKBACK_DAYS=30
TOP_COST_DRIVERS_LIMIT=10
EOF

echo ""
echo "✅  Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Open AI Foundry Portal → Project '$AI_FOUNDRY_PROJECT_NAME' → Overview"
echo "  2. Copy the SDK connection string and paste it into .env"
echo "  3. Deploy a 'gpt-4o' model in your AI Foundry project"
echo "  4. pip install -r requirements.txt"
echo "  5. python -m src.main --interactive"
echo ""
echo "⚠️  .env contains secrets — never commit it to source control."
