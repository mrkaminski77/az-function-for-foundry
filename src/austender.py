from __future__ import annotations

from typing import Any
import json
import os
import requests

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient
from azure.ai.agents.models import ListSortOrder

def _get_austender_ocds_contracts(
    ocds_url: str,
    limit: int = 100,
    timeout: int = 30,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Retrieve government contracts from an AusTender OCDS endpoint.

    Args:
        ocds_url: Full AusTender OCDS API URL (endpoint returning OCDS JSON).
        limit: Max number of contract items to return.
        timeout: HTTP timeout in seconds.
        params: Optional query parameters for filtering/paging.

    Returns:
        A list of normalized contract dicts extracted from OCDS awards.
    """
    query = dict(params or {})
    #response = requests.get(ocds_url, params=query, timeout=timeout)
    #response.raise_for_status()
    #payload = response.json()
    payload = _get_dummy_ocds_response()  # For development/testing without hitting real API
    # OCDS packages can contain "releases" or "records"
    releases: list[dict[str, Any]] = []

    if isinstance(payload, dict):
        if isinstance(payload.get("releases"), list):
            releases = payload["releases"]
        elif isinstance(payload.get("records"), list):
            for record in payload["records"]:
                if isinstance(record, dict):
                    compiled = record.get("compiledRelease")
                    if isinstance(compiled, dict):
                        releases.append(compiled)

    contracts: list[dict[str, Any]] = []
    for release in releases:
        for award in release.get("awards", []) or []:
            contracts.append(
                {
                    "ocid": release.get("ocid"),
                    "releaseId": release.get("id"),
                    "awardId": award.get("id"),
                    "title": award.get("title"),
                    "description": award.get("description"),
                    "status": award.get("status"),
                    "value": (award.get("value") or {}).get("amount"),
                    "currency": (award.get("value") or {}).get("currency"),
                    "date": award.get("date"),
                    "suppliers": [
                        s.get("name") for s in (award.get("suppliers") or []) if isinstance(s, dict)
                    ],
                }
            )
            if len(contracts) >= limit:
                return contracts

    return contracts


def _classify_contract(contract: dict[str, Any]) -> dict[str, Any]:
    def _error_payload(code: str, message: str, details: Any = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": False,
            "result": None,
            "error": {
                "code": code,
                "message": message,
            },
        }
        if details is not None:
            payload["error"]["details"] = str(details)
        return payload

    try:
        endpoint = os.getenv("AZURE_AI_FOUNDRY_ENDPOINT", "").strip().rstrip("/")
        project_name = os.getenv("AZURE_AI_FOUNDRY_PROJECT", "").strip()
        configured_agent_id = os.getenv("AZURE_AI_FOUNDRY_AGENT", "").strip()

        project_endpoint = "https://sra1d-foundry-01.services.ai.azure.com/api/projects/proj-default"
        if endpoint and project_name:
            project_endpoint = f"{endpoint}/api/projects/{project_name}"

        client = AIProjectClient(
            credential=DefaultAzureCredential(),
            endpoint=project_endpoint,
        )

        agent_id = configured_agent_id or "asst_NXAoRTS8nqCoUZTQrM6gP06T"
        agent = client.agents.get_agent(agent_id)
        thread = client.agents.threads.create()

        description = (contract.get("description") or "").strip()
        client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=description,
        )

        run = client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=agent.id,
        )

        if run.status == "failed":
            return _error_payload(
                code="AGENT_RUN_FAILED",
                message="Agent run failed.",
                details=run.last_error,
            )

        messages = client.agents.messages.list(
            thread_id=thread.id,
            order=ListSortOrder.DESCENDING,
        )
        if not messages:
            return _error_payload(
                code="EMPTY_AGENT_RESPONSE",
                message="Agent returned no messages.",
            )

        latest = next(iter(messages), None)
        if latest is None:
            return _error_payload(
                code="NO_AGENT_MESSAGES",
                message="Agent returned no messages.",
            )
        content = latest.content
        response_text = ""

        if isinstance(content, str):
            response_text = content
        elif isinstance(content, list) and content:
            first = content[0]
            text_attr = getattr(first, "text", None)
            if isinstance(text_attr, str):
                response_text = text_attr
            elif text_attr is not None:
                response_text = str(getattr(text_attr, "value", text_attr))
            else:
                response_text = str(first)
        else:
            response_text = str(content)

        try:
            parsed_result = json.loads(response_text)
        except json.JSONDecodeError as ex:
            return _error_payload(
                code="INVALID_JSON_RESPONSE",
                message="Agent response is not valid JSON.",
                details=f"Response text: {response_text}, JSON error: {ex}",
            )

        return {
            "ok": True,
            "result": parsed_result,
            "error": None,
        }
    except Exception as ex:
        return _error_payload(
            code="CLASSIFICATION_EXCEPTION",
            message="Unexpected error while classifying contract.",
            details=ex,
        )


def _get_and_classify_contracts(
    ocds_url: str,
    limit: int = 100,
    timeout: int = 30,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
 
    contracts = _get_austender_ocds_contracts(
        ocds_url=ocds_url,
        limit=limit,
        timeout=timeout,
        params=params,
    )
    results: list[dict[str, Any]] = []
    for contract in contracts:
        classification = _classify_contract(contract)
        results.append(
            {
                "ocid": contract.get("ocid"),
                "classification": classification,
            }
        )

        break

    return results


def _get_dummy_ocds_response() -> dict[str, Any]:
    return {
        "uri": "https://example.local/ocds/releases",
        "version": "1.1",
        "publisher": {
            "name": "AusTender (Dummy)",
            "uri": "https://www.tenders.gov.au",
        },
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "publishedDate": "2026-03-02T00:00:00Z",
        "releases": [
            {
                "ocid": "ocds-dummy-0001",
                "id": "release-0001",
                "date": "2026-03-02T00:00:00Z",
                "tag": ["award"],
                "initiationType": "tender",
                "awards": [
                    {
                        "id": "award-0001",
                        "title": "Dummy Cloud Migration Services",
                        "description": "Development-only sample contract for local testing.",
                        "status": "active",
                        "date": "2026-03-02T00:00:00Z",
                        "value": {
                            "amount": 250000.0,
                            "currency": "AUD",
                        },
                        "suppliers": [
                            {
                                "name": "Dummy Supplier Pty Ltd",
                            }
                        ],
                    }
                ],
            }
        ],
    }

        
            