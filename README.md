# Azure Functions Connectivity Probe (Python)

This project is an Azure Functions Python app designed for **Flex Consumption** deployments.
It exposes one HTTP-triggered function that validates connectivity to:

- Azure Storage (Blob service)
- Azure Key Vault
- Azure AI Foundry Agent project endpoint
- Microsoft Entra ID token issuance
- Microsoft Graph API

## Endpoint

- Route: `/api/connectivity`
- Method: `GET`
- Auth level: `function`

## Local setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `local.settings.json.example` to `local.settings.json` and fill values.
4. Sign in with Azure CLI for local credential resolution:

```bash
az login
```

5. Start Functions runtime:

```bash
func start
```

## Required permissions

Assign your Function App managed identity (or local principal) enough permissions:

- Storage: Data plane role such as `Storage Blob Data Reader` (or higher as needed)
- Key Vault: Secrets read/list permission (RBAC role or access policy)
- Foundry: Access to the project endpoint and agent listing
- Graph API: App permissions/delegated permissions and admin consent appropriate for your selected endpoint

## Notes for Flex Consumption

When creating the Function App in Azure, choose the **Flex Consumption** hosting plan and Python runtime.
Then deploy this project using VS Code Azure Functions extension, Azure Developer CLI, or CI/CD.
