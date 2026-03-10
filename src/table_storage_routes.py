import json
import logging
import traceback
from typing import Any

import azure.functions as func

from src.table_storage_diagnostics import (
    _resolve_table_endpoint,
    enumerate_table_storage,
    list_table_entities,
    list_table_names,
)


table_storage_blueprint = func.Blueprint()


def _to_int(value: str | None, default: int) -> int:
    raw = (value or "").strip()
    if not raw:
        return default
    return int(raw)


@table_storage_blueprint.route(
    route="diagnostics/tables",
    methods=["GET"],
    auth_level=func.AuthLevel.FUNCTION,
)
def get_table_names(req: func.HttpRequest) -> func.HttpResponse:
    try:
        limit = _to_int(req.params.get("limit"), default=50)
        table_names = list_table_names(limit=limit)
        body = {
            "tableEndpoint": _resolve_table_endpoint(),
            "count": len(table_names),
            "items": table_names,
        }
        return func.HttpResponse(body=json.dumps(body, indent=2), status_code=200, mimetype="application/json")
    except ValueError as exc:
        return func.HttpResponse(
            body=json.dumps({"type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}, indent=2),
            status_code=400,
            mimetype="application/json",
        )
    except Exception as exc:
        logging.exception("Failed to list table names")
        return func.HttpResponse(
            body=json.dumps({"type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}, indent=2),
            status_code=500,
            mimetype="application/json",
        )


@table_storage_blueprint.route(
    route="diagnostics/table-entities",
    methods=["GET"],
    auth_level=func.AuthLevel.FUNCTION,
)
def get_table_entities(req: func.HttpRequest) -> func.HttpResponse:
    table_name = (req.params.get("table") or "").strip()
    if not table_name:
        return func.HttpResponse(
            body=json.dumps({"error": "Query parameter 'table' is required."}),
            status_code=400,
            mimetype="application/json",
        )

    try:
        limit = _to_int(req.params.get("limit"), default=50)
        partition_key = (req.params.get("partitionKey") or "").strip() or None
        entities = list_table_entities(table_name=table_name, limit=limit, partition_key=partition_key)
        body: dict[str, Any] = {
            "tableEndpoint": _resolve_table_endpoint(),
            "table": table_name,
            "partitionKey": partition_key,
            "count": len(entities),
            "items": entities,
        }
        return func.HttpResponse(body=json.dumps(body, indent=2), status_code=200, mimetype="application/json")
    except ValueError as exc:
        return func.HttpResponse(
            body=json.dumps({"type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}, indent=2),
            status_code=400,
            mimetype="application/json",
        )
    except Exception as exc:
        logging.exception("Failed to list table entities")
        return func.HttpResponse(
            body=json.dumps({"type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}, indent=2),
            status_code=500,
            mimetype="application/json",
        )


@table_storage_blueprint.route(
    route="diagnostics/table-enumeration",
    methods=["GET"],
    auth_level=func.AuthLevel.FUNCTION,
)
def get_table_enumeration(req: func.HttpRequest) -> func.HttpResponse:
    try:
        table_limit = _to_int(req.params.get("tableLimit"), default=20)
        entity_limit = _to_int(req.params.get("entityLimit"), default=5)
        items = enumerate_table_storage(table_limit=table_limit, entity_limit=entity_limit)
        body = {
            "tableEndpoint": _resolve_table_endpoint(),
            "count": len(items),
            "items": items,
        }
        return func.HttpResponse(body=json.dumps(body, indent=2), status_code=200, mimetype="application/json")
    except ValueError as exc:
        return func.HttpResponse(
            body=json.dumps({"type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}, indent=2),
            status_code=400,
            mimetype="application/json",
        )
    except Exception as exc:
        logging.exception("Failed to enumerate table storage")
        return func.HttpResponse(
            body=json.dumps({"type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}, indent=2),
            status_code=500,
            mimetype="application/json",
        )
