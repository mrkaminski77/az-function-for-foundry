from __future__ import annotations

from typing import Any
import os

from azure.data.tables import TableServiceClient
from azure.identity import DefaultAzureCredential


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


def _create_table_service_client() -> TableServiceClient:
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    return TableServiceClient(endpoint=_resolve_table_endpoint(), credential=credential)


def _to_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_json_safe(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def list_table_names(limit: int = 50) -> list[str]:
    safe_limit = max(1, min(limit, 200))
    service = _create_table_service_client()

    names: list[str] = []
    for index, table in enumerate(service.list_tables()):
        if index >= safe_limit:
            break
        table_name = str(table.get("name") or "")
        if table_name:
            names.append(table_name)

    return names


def list_table_entities(
    table_name: str,
    limit: int = 50,
    partition_key: str | None = None,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 200))
    cleaned_table_name = (table_name or "").strip()
    if not cleaned_table_name:
        raise ValueError("table_name is required")

    service = _create_table_service_client()
    table_client = service.get_table_client(table_name=cleaned_table_name)

    entities: list[dict[str, Any]] = []
    if partition_key:
        escaped_partition = partition_key.replace("'", "''")
        iterator = table_client.query_entities(query_filter=f"PartitionKey eq '{escaped_partition}'")
    else:
        iterator = table_client.list_entities()

    for index, entity in enumerate(iterator):
        if index >= safe_limit:
            break
        entities.append(_to_json_safe(dict(entity)))

    return entities


def enumerate_table_storage(table_limit: int = 20, entity_limit: int = 5) -> list[dict[str, Any]]:
    tables = list_table_names(limit=table_limit)

    output: list[dict[str, Any]] = []
    for table_name in tables:
        entities = list_table_entities(table_name=table_name, limit=entity_limit)
        output.append(
            {
                "tableName": table_name,
                "entityCountReturned": len(entities),
                "entities": entities,
            }
        )

    return output
