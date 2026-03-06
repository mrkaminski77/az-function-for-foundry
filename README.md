# Azure Functions Connectivity Probe (Python)

This project is an Azure Functions Python app designed for **Flex Consumption** deployments.
It exposes:

- one HTTP-triggered function set for OCDS classification and run history
- one timer-triggered orchestration function to run periodic checks for AusTender
- one HTTP-triggered connectivity function that validates connectivity to:

- Azure Storage (Blob service)
- Azure Key Vault
- Azure AI Foundry Agent project endpoint
- Microsoft Entra ID token issuance
- Microsoft Graph API

## Endpoint

- Route: `/api/connectivity`
- Method: `GET`
- Auth level: `function`

## OCDS Classification Triggers

- HTTP route: `/api/ocds/classify?source=<key>`
- HTTP route (explicit testing window): `/api/ocds/classify-range?source=<key>&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- Run summary route: `/api/ocds/runs?limit=20&source=<key>`
- Configured sources route: `/api/ocds/sources`

Date-range behavior:

- `/api/ocds/classify` supports optional `start_date` and `end_date` query params (must be provided together).
- If no date range is supplied, pipeline uses watermark/default lookback behavior.
- If a date range is supplied, the run uses that range and does not update watermark.
- `/api/ocds/classify-range` requires both `start_date` and `end_date` and always skips watermark updates.

Timer trigger functions:

- `orchestrate_austender` → AusTender default source using `AUSTENDER_CHECK_SCHEDULE`

Default schedule in `local.settings.json.example` is every 6 hours:

```text
0 0 */6 * * *
```

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

### Environment variables (Foundry)

- `AZURE_AI_FOUNDRY_ENDPOINT` - Foundry resource endpoint (without `/api/projects/...`)
- `AZURE_AI_FOUNDRY_PROJECT` - Foundry project name
- `AZURE_AI_FOUNDRY_CLASSIFIER_AGENT` - agent ID used for contract classification

Compatibility note: code still accepts `AZURE_AI_FOUNDRY_AGENT` as a legacy fallback.

### Environment variables (AusTender)

- `AUSTENDER_OCDS_URL` - default OCDS endpoint base URL
- `AUSTENDER_OCDS_URL_<SOURCE_KEY>` - source-specific endpoint URL used when `source=<SOURCE_KEY>` is passed (example: `AUSTENDER_OCDS_URL_HEALTH`)
- `AUSTENDER_CHECK_SCHEDULE` - NCRONTAB schedule for the timer orchestration
- `AUSTENDER_RUN_LOG_TABLE` - Optional table name for per-run execution summaries (default: `OcdsRunHistory`)

### Environment variables (EWS result delivery)

- `RESULTS_SENDER_PROVIDER` - Sender provider (`ews`, `graph`, or `none`), default `ews`
- `EWS_SEND_RESULTS_ENABLED` - Enables sending timer run results over Exchange EWS when set to `true`
- `GRAPH_SEND_RESULTS_ENABLED` - Enables Graph sender execution once Graph implementation is completed
- `EWS_TENANT_ID` - Microsoft Entra tenant ID used for OAuth2 client credentials
- `EWS_SENDER_EMAIL` - Mailbox SMTP address used to send results
- `EWS_RECIPIENTS` - Comma-separated list of recipient email addresses
- `EWS_CLIENT_ID_SECRET_NAME` - Key Vault secret name that stores the Entra app `clientId`
- `EWS_CLIENT_SECRET_SECRET_NAME` - Key Vault secret name that stores the Entra app `clientSecret`
- `EWS_SERVER` - EWS hostname (default: `outlook.office365.com`)
- `EWS_ACCESS_TYPE` - `IMPERSONATION` (default) or `DELEGATE`
- `EWS_SUBJECT_PREFIX` - Optional subject prefix for notification emails

Implementation notes:

- Timer orchestration now calls `send_classification_results` after classification.
- Credentials are loaded from Azure Key Vault using `DefaultAzureCredential`.
- Provider dispatch is in `src/result_sender.py`.
- EWS delivery is implemented in `src/ews_sender.py`.
- Graph sender has a scaffold in `src/graph_sender.py` and is designed for future implementation.

Source notes:

- if `source` is omitted, the default key is `DEFAULT` and `AUSTENDER_OCDS_URL` is used
- source values are normalized to uppercase and non-alphanumeric chars become `_`
- watermarking, dedupe partitioning, and run logs are scoped by normalized source key

### Table Storage Defaults

- Classification results table: `OcdsClassifications`
- Run summary table: `OcdsRunHistory`
- Optional override: `AUSTENDER_RUN_LOG_TABLE` (overrides only the run summary table name)

## Run Audit Logging

Each HTTP or timer invocation of the OCDS classification pipeline writes a summary row to Azure Table Storage (`OcdsRunHistory` by default), including:

- run start/end UTC timestamps and duration
- status (`Succeeded`/`Failed`)
- date filter window used for OCDS fetch
- fetched/processed/skipped/failure counts
- top-level error message when a run fails

## Required permissions

Assign your Function App managed identity (or local principal) enough permissions:

- Storage: Data plane role such as `Storage Blob Data Reader` (or higher as needed)
- Key Vault: Secrets read/list permission (RBAC role or access policy)
- Foundry: Access to the project endpoint and agent listing
- Graph API: App permissions/delegated permissions and admin consent appropriate for your selected endpoint

## Notes for Flex Consumption

When creating the Function App in Azure, choose the **Flex Consumption** hosting plan and Python runtime.
Then deploy this project using VS Code Azure Functions extension, Azure Developer CLI, or CI/CD.
