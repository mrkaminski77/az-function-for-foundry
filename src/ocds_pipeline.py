from __future__ import annotations

from typing import Any
import json
import os
import requests
import logging
import re
import hashlib
from datetime import datetime, timedelta, timezone

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient
from azure.ai.agents.models import ListSortOrder

from azure.data.tables import TableClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError, HttpResponseError
import uuid

import random


def _resolve_table_endpoint() -> str:
    table_endpoint = os.getenv("TABLE_ACCOUNT_URL", "").strip().rstrip("/")
    if table_endpoint:
        return table_endpoint

    storage_endpoint = os.getenv("STORAGE_ACCOUNT_URL", "").strip().rstrip("/")
    if not storage_endpoint:
        raise ValueError("Missing TABLE_ACCOUNT_URL (or STORAGE_ACCOUNT_URL fallback)")

    if ".blob." in storage_endpoint:
        return storage_endpoint.replace(".blob.", ".table.")

    return storage_endpoint


def _normalize_source_key(source_key: str | None) -> str:
    candidate = (source_key or "").strip().upper()
    if not candidate:
        return "DEFAULT"

    normalized = re.sub(r"[^A-Z0-9]+", "_", candidate).strip("_")
    return normalized or "DEFAULT"


def _sanitize_table_key(raw: str | None, fallback: str) -> str:
    candidate = str(raw or "").strip()
    if not candidate:
        return fallback

    sanitized = re.sub(r"[\\/#?\x00-\x1F\x7F]+", "_", candidate)
    return sanitized.strip() or fallback


def _build_award_row_key(contract: dict[str, Any]) -> str:
    award_id = _sanitize_table_key(contract.get("awardId"), "")
    if award_id:
        return award_id

    stable_source = "|".join(
        [
            str(contract.get("ocid") or ""),
            str(contract.get("releaseId") or ""),
            str(contract.get("title") or ""),
            str(contract.get("date") or ""),
            str(contract.get("description") or ""),
        ]
    )
    digest = hashlib.sha256(stable_source.encode("utf-8")).hexdigest()[:16]
    return f"missing_awardid_{digest}"


def _get_watermark(
    table_client: TableClient,
    date_type: str,
    source_key: str = "DEFAULT",
) -> str | None:
    try:
        entity = table_client.get_entity(
            partition_key="__meta__",
            row_key=f"watermark_{source_key}_{date_type}",
        )
    except ResourceNotFoundError:
        return None

    watermark = entity.get("Watermark")
    if not isinstance(watermark, str):
        return None
    return watermark.strip() or None


def _set_watermark(
    table_client: TableClient,
    date_type: str,
    watermark: str,
    source_key: str = "DEFAULT",
) -> None:
    table_client.upsert_entity(
        mode="Replace",
        entity={
            "PartitionKey": "__meta__",
            "RowKey": f"watermark_{source_key}_{date_type}",
            "Watermark": watermark,
            "LastUpdatedUtc": datetime.now(timezone.utc).isoformat(),
        },
    )


def _resolve_run_log_table_name() -> str:
    configured = os.getenv("AUSTENDER_RUN_LOG_TABLE", "").strip()
    return configured or "OcdsRunHistory"


def _create_table_client(table_name: str) -> TableClient:
    table_client = TableClient(
        endpoint=_resolve_table_endpoint(),
        table_name=table_name,
        credential=DefaultAzureCredential(),
    )
    try:
        table_client.create_table()
    except ResourceExistsError:
        pass
    return table_client


def _write_run_summary(
    table_client: TableClient | None,
    run_id: str,
    started_at_utc: datetime,
    completed_at_utc: datetime,
    status: str,
    date_type: str,
    start_date: str,
    end_date: str,
    fetched_count: int,
    processed_count: int,
    skipped_existing_count: int,
    classification_failure_count: int,
    error_message: str | None,
    source_key: str,
    ocds_url: str,
) -> None:
    if table_client is None:
        return

    duration_seconds = max((completed_at_utc - started_at_utc).total_seconds(), 0.0)
    entity: dict[str, Any] = {
        "PartitionKey": f"{source_key}|{started_at_utc.date().isoformat()}",
        "RowKey": run_id,
        "RunId": run_id,
        "SourceKey": source_key,
        "OcdsUrl": ocds_url,
        "StartedUtc": started_at_utc.isoformat(),
        "CompletedUtc": completed_at_utc.isoformat(),
        "DurationSeconds": duration_seconds,
        "Status": status,
        "DateType": date_type,
        "StartDate": start_date,
        "EndDate": end_date,
        "FetchedCount": fetched_count,
        "ProcessedCount": processed_count,
        "SkippedExistingCount": skipped_existing_count,
        "ClassificationFailureCount": classification_failure_count,
    }
    if error_message:
        entity["ErrorMessage"] = error_message[:1000]

    table_client.create_entity(entity=entity)


def _get_recent_run_summaries(limit: int = 20, source_key: str | None = None) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 100))
    table_name = _resolve_run_log_table_name()

    try:
        table_client = _create_table_client(table_name=table_name)
    except Exception as ex:
        raise RuntimeError(
            f"Failed to access run log table '{table_name}'."
        ) from ex

    filter_source = _normalize_source_key(source_key) if source_key else None

    entities = list(table_client.list_entities())
    if filter_source:
        entities = [entity for entity in entities if entity.get("SourceKey") == filter_source]
    entities.sort(key=lambda item: str(item.get("StartedUtc", "")), reverse=True)

    summaries: list[dict[str, Any]] = []
    for entity in entities[:safe_limit]:
        summaries.append(
            {
                "runId": entity.get("RunId"),
                "sourceKey": entity.get("SourceKey"),
                "ocdsUrl": entity.get("OcdsUrl"),
                "startedUtc": entity.get("StartedUtc"),
                "completedUtc": entity.get("CompletedUtc"),
                "durationSeconds": entity.get("DurationSeconds"),
                "status": entity.get("Status"),
                "dateType": entity.get("DateType"),
                "startDate": entity.get("StartDate"),
                "endDate": entity.get("EndDate"),
                "fetchedCount": entity.get("FetchedCount"),
                "processedCount": entity.get("ProcessedCount"),
                "skippedExistingCount": entity.get("SkippedExistingCount"),
                "classificationFailureCount": entity.get("ClassificationFailureCount"),
                "errorMessage": entity.get("ErrorMessage"),
            }
        )

    return summaries


def _get_ocds_contracts_by_date(
    ocds_url: str,
    limit: int = 100,
    timeout: int = 30,
    date_type: str = "contractLastModified",
    start_date: str = None,
    end_date: str = None,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Retrieve government contracts from an AusTender OCDS endpoint.

    Args:
        ocds_url: Full OCDS API URL (endpoint returning OCDS JSON).
        limit: Max number of contract items to return.
        timeout: HTTP timeout in seconds.
        date_type: Type of date to filter contracts by (e.g., "contractLastModified").
        start_date: Start date for filtering contracts (inclusive).
        end_date: End date for filtering contracts (inclusive).

    Returns:
        A list of normalized contract dicts extracted from OCDS awards.
    """
    if not start_date or not end_date:
        raise ValueError("Both start_date and end_date are required.")

    request_url = f"{ocds_url}/{date_type}/{start_date}/{end_date}"
    query_params: dict[str, Any] = dict(params or {})
    query_params.setdefault("limit", limit)

    response = requests.get(request_url, params=query_params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    #payload = _get_dummy_ocds_response()  # For development/testing without hitting real API
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
        configured_agent_id = os.getenv(
            "AZURE_AI_FOUNDRY_CLASSIFIER_AGENT",
            os.getenv("AZURE_AI_FOUNDRY_AGENT", ""),
        ).strip()

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
    source_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    update_watermark: bool | None = None,
) -> list[dict[str, Any]]:
    table_name = "OcdsClassifications"
    table_endpoint = _resolve_table_endpoint()
    source_scope = _normalize_source_key(source_key)

    try:
        table_client = _create_table_client(table_name=table_name)
    except HttpResponseError as ex:
        raise RuntimeError(
            f"Failed to access/create table '{table_name}' at endpoint '{table_endpoint}'. "
            f"Verify TABLE_ACCOUNT_URL points to a Table endpoint (*.table.core.windows.net)."
        ) from ex

    run_log_client: TableClient | None = None
    run_log_table_name = _resolve_run_log_table_name()
    try:
        run_log_client = _create_table_client(table_name=run_log_table_name)
    except Exception as ex:
        logging.warning(
            "Run summary logging disabled: failed to access table '%s'. Error: %s",
            run_log_table_name,
            ex,
        )

    run_id = str(uuid.uuid4())
    started_at_utc = datetime.now(timezone.utc)
    status = "Succeeded"
    error_message: str | None = None
    fetched_count = 0
    processed_count = 0
    skipped_existing_count = 0
    classification_failure_count = 0

    date_type = "contractLastModified"
    explicit_range = bool(start_date and end_date)
    if bool(start_date) != bool(end_date):
        raise ValueError("Both start_date and end_date must be provided together.")

    if explicit_range:
        effective_start_date = str(start_date).strip()
        effective_end_date = str(end_date).strip()
    else:
        watermark = _get_watermark(table_client=table_client, date_type=date_type, source_key=source_scope)
        initial_lookback_days = int(os.getenv("AUSTENDER_INITIAL_LOOKBACK_DAYS", "1"))

        now_utc = datetime.now(timezone.utc).date()
        effective_end_date = now_utc.isoformat()
        default_start_date = (now_utc - timedelta(days=max(initial_lookback_days, 1))).isoformat()
        effective_start_date = watermark or default_start_date

    should_update_watermark = update_watermark if update_watermark is not None else (not explicit_range)

    try:
        contracts = _get_ocds_contracts_by_date(
            ocds_url=ocds_url,
            limit=limit,
            timeout=timeout,
            date_type=date_type,
            start_date=effective_start_date,
            end_date=effective_end_date,
            params=params,
        )
        fetched_count = len(contracts)

        results: list[dict[str, Any]] = []
        for contract in contracts:
            award_row_key = _build_award_row_key(contract)
            if not contract.get("awardId"):
                logging.warning(
                    "Award is missing id. Using generated row key. source=%s ocid=%s rowKey=%s",
                    source_scope,
                    contract.get("ocid"),
                    award_row_key,
                )

            table_entity = {
                "PartitionKey": f"{source_scope}|{contract.get('ocid', 'unknown_ocid')}",
                "RowKey": award_row_key,
            }
            try:
                table_client.get_entity(
                    partition_key=table_entity["PartitionKey"],
                    row_key=table_entity["RowKey"],
                )
                logging.info(
                    "Skipping existing award classification. source=%s ocid=%s awardId=%s rowKey=%s",
                    source_scope,
                    contract.get("ocid"),
                    contract.get("awardId"),
                    table_entity["RowKey"],
                )
                skipped_existing_count += 1
                continue
            except ResourceNotFoundError:
                pass

            classification = _classify_contract(contract)
            if not classification.get("ok", False):
                classification_failure_count += 1
                error_code = (classification.get("error") or {}).get("code")
                logging.warning(
                    "Award classification failed. source=%s ocid=%s awardId=%s rowKey=%s errorCode=%s",
                    source_scope,
                    contract.get("ocid"),
                    contract.get("awardId"),
                    table_entity["RowKey"],
                    error_code,
                )
            else:
                logging.info(
                    "Award classification succeeded. source=%s ocid=%s awardId=%s rowKey=%s",
                    source_scope,
                    contract.get("ocid"),
                    contract.get("awardId"),
                    table_entity["RowKey"],
                )

            table_entity["ClassificationResult"] = json.dumps(classification)

            try:
                table_client.create_entity(entity=table_entity)
            except Exception as ex:
                raise RuntimeError(
                    f"Failed to create table entity for ocid={contract.get('ocid')} "
                    f"awardId={contract.get('awardId')}"
                ) from ex

            processed_count += 1
            results.append(
                {
                    "ocid": contract.get("ocid"),
                    "awardId": contract.get("awardId"),
                    "rowKey": table_entity["RowKey"],
                    "sourceKey": source_scope,
                    "classification": classification,
                    "awardDescription": contract.get("description")
                }
            )

        if should_update_watermark:
            _set_watermark(
                table_client=table_client,
                date_type=date_type,
                watermark=effective_end_date,
                source_key=source_scope,
            )
        else:
            logging.info(
                "Watermark update skipped for explicit date-range run. source=%s start_date=%s end_date=%s",
                source_scope,
                effective_start_date,
                effective_end_date,
            )

        return results
    except Exception as ex:
        status = "Failed"
        error_message = f"{type(ex).__name__}: {ex}"
        raise
    finally:
        completed_at_utc = datetime.now(timezone.utc)
        try:
            _write_run_summary(
                table_client=run_log_client,
                run_id=run_id,
                started_at_utc=started_at_utc,
                completed_at_utc=completed_at_utc,
                status=status,
                date_type=date_type,
                start_date=effective_start_date,
                end_date=effective_end_date,
                fetched_count=fetched_count,
                processed_count=processed_count,
                skipped_existing_count=skipped_existing_count,
                classification_failure_count=classification_failure_count,
                error_message=error_message,
                source_key=source_scope,
                ocds_url=ocds_url,
            )
        except Exception:
            logging.exception("Failed to write AusTender run summary for run_id=%s", run_id)


