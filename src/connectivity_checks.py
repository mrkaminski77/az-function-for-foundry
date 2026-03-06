import json
import logging
import os
import requests
import time
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient
from azure.ai.agents.models import ListSortOrder


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
    agent_id = os.getenv(
        "AZURE_AI_FOUNDRY_CLASSIFIER_AGENT",
        os.getenv("AZURE_AI_FOUNDRY_AGENT", ""),
    ).strip()
    project_endpoint = f"{endpoint}/api/projects/{project}"
    project_endpoint = "https://sra1d-foundry-01.services.ai.azure.com/api/projects/proj_default"
    prompt = "Hello Agent, this is a connectivity test. Please respond with OK."

    project = AIProjectClient(
        credential=DefaultAzureCredential(),
        endpoint="https://sra1d-foundry-01.services.ai.azure.com/api/projects/proj-default")

    agent = project.agents.get_agent("asst_NXAoRTS8nqCoUZTQrM6gP06T")
    # create a thread
    thread = project.agents.threads.create()

    # post a message to the thread
    message = project.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content=prompt
    )
    # process the thread using the specified agent
    run = project.agents.runs.create_and_process(
    thread_id=thread.id,
    agent_id=agent.id)
    result = None
    if run.status == "failed":
        print(f"Run failed: {run.last_error}")
    else:
        messages = project.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)

        for message in messages:
            if message.text_messages:
                result = (f"{message.role}: {message.text_messages[-1].text.value}")

    stop = time.perf_counter()
    details = {
        "endpoint": endpoint,
        "project": project_endpoint,
        "agentId": agent_id,
        "prompt": prompt,
        "runStatus": run.status,
        "agentResponse": result
    }
    return _result("foundryAgent", True, details, (stop - start) * 1000)


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
