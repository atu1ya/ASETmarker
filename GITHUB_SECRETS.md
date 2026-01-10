# GitHub Secrets Configuration Guide

This guide provides step-by-step instructions for configuring GitHub Secrets required for automated deployment to Azure.

## Required GitHub Secrets

Your GitHub Actions workflow requires 5 secrets. Here's how to obtain and configure each one.

---

## 1. AZURE_CREDENTIALS

**Description:** Service principal credentials for GitHub Actions to authenticate with Azure.

**How to Obtain:**

```bash
# Replace with your subscription ID and resource group name
SUBSCRIPTION_ID="<your-subscription-id>"
RESOURCE_GROUP="asetmarker-rg"

# Create service principal
az ad sp create-for-rbac \
  --name "asetmarker-github-actions" \
  --role Contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP \
  --sdk-auth
```

**Expected Output:**
```json
{
  "clientId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "clientSecret": "xxxxxxxxxxxxxxxxxxxxxxxxxx",
  "subscriptionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
  "resourceManagerEndpointUrl": "https://management.azure.com/",
  "activeDirectoryGraphResourceId": "https://graph.windows.net/",
  "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
  "galleryEndpointUrl": "https://gallery.azure.com/",
  "managementEndpointUrl": "https://management.core.windows.net/"
}
```

**GitHub Secret Value:** Copy the entire JSON output

---

## 2. REGISTRY_LOGIN_SERVER

**Description:** The URL of your Azure Container Registry.

**How to Obtain:**

```bash
ACR_NAME="asetmarkeracr"  # Your ACR name

az acr show --name $ACR_NAME --query loginServer -o tsv
```

**Expected Output:** `asetmarkeracr.azurecr.io`

**GitHub Secret Value:** The full URL (e.g., `asetmarkeracr.azurecr.io`)

---

## 3. REGISTRY_USERNAME

**Description:** Admin username for Azure Container Registry.

**How to Obtain:**

```bash
ACR_NAME="asetmarkeracr"  # Your ACR name

az acr credential show --name $ACR_NAME --query username -o tsv
```

**Expected Output:** `asetmarkeracr`

**GitHub Secret Value:** The username returned

**Note:** Ensure ACR admin access is enabled:
```bash
az acr update --name $ACR_NAME --admin-enabled true
```

---

## 4. REGISTRY_PASSWORD

**Description:** Admin password for Azure Container Registry.

**How to Obtain:**

```bash
ACR_NAME="asetmarkeracr"  # Your ACR name

az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv
```

**Expected Output:** A long alphanumeric password

**GitHub Secret Value:** The password returned

---

## 5. WEBAPP_NAME

**Description:** The name of your Azure Web App.

**How to Obtain:**

This is the name you chose when creating the Web App:

```bash
WEBAPP_NAME="asetmarker-webapp"  # Your Web App name
```

**GitHub Secret Value:** The Web App name (e.g., `asetmarker-webapp`)

**Verify it exists:**
```bash
az webapp show --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP --query name -o tsv
```

---

## Adding Secrets to GitHub

1. Navigate to your GitHub repository
2. Click **Settings** (top navigation)
3. In the left sidebar, expand **Secrets and variables** → click **Actions**
4. Click **New repository secret**
5. For each secret:
   - Enter the **Name** (exactly as shown above)
   - Paste the **Secret value**
   - Click **Add secret**

### Visual Steps:

```
GitHub Repository
└── Settings
    └── Secrets and variables
        └── Actions
            └── New repository secret
                ├── Name: AZURE_CREDENTIALS
                ├── Secret: {paste JSON}
                └── Add secret
```

---

## Verification Checklist

Before triggering deployment, verify all secrets are configured:

- [ ] `AZURE_CREDENTIALS` - Full JSON output from service principal
- [ ] `REGISTRY_LOGIN_SERVER` - ACR URL (e.g., `asetmarkeracr.azurecr.io`)
- [ ] `REGISTRY_USERNAME` - ACR admin username
- [ ] `REGISTRY_PASSWORD` - ACR admin password
- [ ] `WEBAPP_NAME` - Azure Web App name

---

## Testing the Setup

### Manual Workflow Trigger

1. Go to **Actions** tab in GitHub
2. Select **Build and Deploy to Azure Web App** workflow
3. Click **Run workflow** → **Run workflow**
4. Monitor the workflow execution

### Expected Workflow Steps:

```
✓ Checkout code
✓ Log in to Azure
✓ Log in to Azure Container Registry
✓ Build and push Docker image
✓ Deploy to Azure Web App
✓ Azure logout
```

---

## Troubleshooting

### "Error: Login failed with Error: ..."

**Cause:** `AZURE_CREDENTIALS` is incorrect or service principal lacks permissions.

**Solution:**
- Verify the JSON is complete and unmodified
- Ensure service principal has Contributor role
- Recreate service principal if needed

### "Error: Error response from daemon: unauthorized"

**Cause:** `REGISTRY_USERNAME` or `REGISTRY_PASSWORD` is incorrect.

**Solution:**
- Verify ACR admin access is enabled
- Regenerate credentials: `az acr credential show --name $ACR_NAME`
- Update GitHub secrets with new values

### "Error: Resource not found"

**Cause:** `WEBAPP_NAME` is incorrect or Web App doesn't exist.

**Solution:**
- Verify Web App exists: `az webapp list --query "[].name" -o table`
- Check resource group is correct
- Update `WEBAPP_NAME` secret

---

## Security Best Practices

1. **Rotate credentials regularly:** Update service principal and ACR passwords every 90 days
2. **Limit scope:** Service principal should only have access to necessary resource groups
3. **Audit access:** Review Azure Activity Logs for unauthorized access attempts
4. **Secret rotation:** When rotating, update GitHub Secrets immediately
5. **Backup credentials:** Store credentials securely (e.g., Azure Key Vault) for disaster recovery

---

## Quick Reference Commands

### Get All Required Values at Once

```bash
# Set your variables
SUBSCRIPTION_ID="<your-subscription-id>"
RESOURCE_GROUP="asetmarker-rg"
ACR_NAME="asetmarkeracr"
WEBAPP_NAME="asetmarker-webapp"

# Get all values
echo "=== AZURE_CREDENTIALS ==="
az ad sp create-for-rbac \
  --name "asetmarker-github-actions" \
  --role Contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP \
  --sdk-auth

echo ""
echo "=== REGISTRY_LOGIN_SERVER ==="
az acr show --name $ACR_NAME --query loginServer -o tsv

echo ""
echo "=== REGISTRY_USERNAME ==="
az acr credential show --name $ACR_NAME --query username -o tsv

echo ""
echo "=== REGISTRY_PASSWORD ==="
az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv

echo ""
echo "=== WEBAPP_NAME ==="
echo $WEBAPP_NAME
```

Save this output securely and use it to configure GitHub Secrets.
