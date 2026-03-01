import json
import logging
import os
import time
from typing import Any

import azure.functions as func
import requests
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


def _result(name: str, ok: bool, details: dict[str, Any], elapsed_ms: float) -> dict[str, Any]:
    return {
        "name": name,
        "ok": ok,
        "elapsedMs": round(elapsed_ms, 2),
        "details": details,
    }


def _check_storage(credential: DefaultAzureCredential) -> dict[str, Any]:
    start = time.perf_counter()
    account_url = os.getenv("STORAGE_ACCOUNT_URL", "").strip()
    if not account_url:
        raise ValueError("Missing STORAGE_ACCOUNT_URL")

    client = BlobServiceClient(account_url=account_url, credential=credential)

    # Use an AAD/RBAC-friendly data-plane operation
    first_container = next(client.list_containers(results_per_page=1), None)

    details = {
        "accountUrl": account_url,
        "canListContainers": True,
        "firstContainerName": first_container.get("name") if first_container else None,
    }
    return _result("storage", True, details, (time.perf_counter() - start) * 1000)    


def _check_key_vault(credential: DefaultAzureCredential) -> dict[str, Any]:
    start = time.perf_counter()
    vault_url = os.getenv("KEY_VAULT_URL", "").strip()
    secret_name = os.getenv("KEY_VAULT_SECRET_NAME", "").strip()
    if not vault_url:
        raise ValueError("Missing KEY_VAULT_URL")

    client = SecretClient(vault_url=vault_url, credential=credential)

    if secret_name:
        secret = client.get_secret(secret_name)
        details = {
            "vaultUrl": vault_url,
            "secretName": secret.name,
            "secretVersion": secret.properties.version,
        }
    else:
        iterator = client.list_properties_of_secrets()
        first = next(iterator, None)
        details = {
            "vaultUrl": vault_url,
            "listedAtLeastOneSecret": first is not None,
        }

    return _result("keyVault", True, details, (time.perf_counter() - start) * 1000)


def _check_foundry_agent(credential: DefaultAzureCredential) -> dict[str, Any]:
    start = time.perf_counter()
    endpoint = os.getenv("AZURE_AI_FOUNDRY_ENDPOINT", "").strip().rstrip("/")
    project = os.getenv("AZURE_AI_FOUNDRY_PROJECT", "").strip()
    agent = os.getenv("AZURE_AI_FOUNDRY_AGENT", "").strip()
    api_version = os.getenv("AZURE_AI_FOUNDRY_API_VERSION", "2024-10-01-preview").strip()
    vault_url = os.getenv("KEY_VAULT_URL", "").strip()
    secret_name = os.getenv("KEY_VAULT_SECRET_NAME", "").strip()

    if not endpoint:
        raise ValueError("Missing AZURE_AI_FOUNDRY_ENDPOINT")
    if not project:
        raise ValueError("Missing AZURE_AI_FOUNDRY_PROJECT")
    if not agent:
        raise ValueError("Missing AZURE_AI_FOUNDRY_AGENT")
    if not vault_url:
        raise ValueError("Missing KEY_VAULT_URL")
    if not secret_name:
        raise ValueError("Missing KEY_VAULT_SECRET_NAME")

    kv_client = SecretClient(vault_url=vault_url, credential=credential)
    foundry_key = kv_client.get_secret(secret_name).value
    if not foundry_key:
        raise ValueError(f"Secret '{secret_name}' has no value")

    # Invoke specific agent
    #https://sra1d-foundry-01.services.ai.azure.com/api/projects/proj-default
    invoke_url = f"{endpoint}/api/projects/{project}/agents/{agent}:invoke?api-version={api_version}"

    headers = {
        "api-key": foundry_key,
        "Content-Type": "application/json",
    }
    payload = {
        "input": "Hello, Agent! This is a connectivity test."
        # If your API expects messages, switch to:
        # "messages": [{"role": "user", "content": "Hello, Agent! This is a connectivity test."}]
    }

    response = requests.post(invoke_url, headers=headers, json=payload, timeout=20)
    ok = 200 <= response.status_code < 300

    details = {
        "invokeUrl": invoke_url,
        "statusCode": response.status_code,
        "responsePreview": response.text[:500],
    }

    if not ok:
        raise RuntimeError(json.dumps(details))

    return _result("foundryAgent", True, details, (time.perf_counter() - start) * 1000)

def _check_entra(credential: DefaultAzureCredential) -> tuple[dict[str, Any], str]:
    start = time.perf_counter()
    scope = os.getenv("ENTRA_TEST_SCOPE", "https://graph.microsoft.com/.default")
    token = credential.get_token(scope)
    details = {
        "scope": scope,
        "tokenExpiresOn": token.expires_on,
    }
    result = _result("entra", True, details, (time.perf_counter() - start) * 1000)
    return result, token.token


def _check_graph(access_token: str) -> dict[str, Any]:
    start = time.perf_counter()
    graph_url = os.getenv("GRAPH_API_URL", "https://graph.microsoft.com/v1.0/").strip()

    response = requests.get(
        graph_url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )

    ok = 200 <= response.status_code < 300
    details = {
        "graphUrl": graph_url,
        "statusCode": response.status_code,
    }

    if not ok:
        details["responsePreview"] = response.text[:500]
        raise RuntimeError(json.dumps(details))

    return _result("graphApi", True, details, (time.perf_counter() - start) * 1000)


@app.route(route="connectivity", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def connectivity(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Connectivity test function started.")

    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)

    checks: list[dict[str, Any]] = []
    access_token = ""

    for name, check in [
        ("storage", lambda: _check_storage(credential)),
        ("keyVault", lambda: _check_key_vault(credential)),
        ("foundryAgent", lambda: _check_foundry_agent(credential)),
    ]:
        try:
            checks.append(check())
        except Exception as exc:
            checks.append(_result(name, False, {"error": str(exc)}, 0))

    try:
        entra_result, access_token = _check_entra(credential)
        checks.append(entra_result)
    except Exception as exc:
        checks.append(_result("entra", False, {"error": str(exc)}, 0))

    if access_token:
        try:
            checks.append(_check_graph(access_token))
        except Exception as exc:
            checks.append(_result("graphApi", False, {"error": str(exc)}, 0))
    else:
        checks.append(_result("graphApi", False, {"error": "Skipped because Entra token acquisition failed"}, 0))

    overall_ok = all(item["ok"] for item in checks)

    body = {
        "overallOk": overall_ok,
        "timestampUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checks": checks,
    }

    return func.HttpResponse(
        body=json.dumps(body, indent=2),
        status_code=200 if overall_ok else 500,
        mimetype="application/json",
    )
