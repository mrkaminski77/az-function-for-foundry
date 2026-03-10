import json
import logging
import os
import re
import traceback
from datetime import date
from typing import Any

import azure.functions as func

from src.ocds_pipeline import _get_and_classify_contracts, _get_recent_run_summaries

ocds_blueprint = func.Blueprint()


def _normalize_source_param(value: str | None) -> str:
    candidate = (value or "").strip().upper()
    if not candidate:
        raise ValueError("Query parameter 'source' is required.")

    normalized = re.sub(r"[^A-Z0-9]+", "_", candidate).strip("_")
    if not normalized:
        raise ValueError("Query parameter 'source' must contain at least one alphanumeric character.")

    return normalized


def _resolve_source_env(source: str | None) -> tuple[str, str, str]:
    source_key = _normalize_source_param(source)

    env_var_name = f"{source_key}_OCDS_URL"

    ocds_url = os.getenv(env_var_name, "").strip()
    if not ocds_url:
        raise ValueError(f"Missing required environment variable '{env_var_name}'")

    schedule_env_var_name = f"{source_key}_CHECK_SCHEDULE"
    return source_key, env_var_name, schedule_env_var_name


def _resolve_ocds_url_for_source(source: str | None) -> tuple[str, str, str, str]:
    source_key, env_var_name, schedule_env_var_name = _resolve_source_env(source)
    ocds_url = os.getenv(env_var_name, "").strip()
    return source_key, env_var_name, schedule_env_var_name, ocds_url


def _run_ocds_classification(source: str | None) -> tuple[str, str, list[dict[str, Any]]]:
    source_key, env_var_name, _, ocds_url = _resolve_ocds_url_for_source(source)
    results = _get_and_classify_contracts(ocds_url=ocds_url, source_key=source_key)
    return source_key, env_var_name, results


def _validate_date_range(start_date: str | None, end_date: str | None) -> tuple[str | None, str | None]:
    start = (start_date or "").strip()
    end = (end_date or "").strip()

    if not start and not end:
        return None, None

    if not start or not end:
        raise ValueError("Query parameters 'start_date' and 'end_date' must be provided together.")

    try:
        start_value = date.fromisoformat(start)
        end_value = date.fromisoformat(end)
    except ValueError as ex:
        raise ValueError("Query parameters 'start_date' and 'end_date' must be ISO dates (YYYY-MM-DD).") from ex

    if start_value > end_value:
        raise ValueError("Query parameter 'start_date' must be less than or equal to 'end_date'.")

    return start, end


def _run_ocds_classification_with_range(
    source: str | None,
    start_date: str | None,
    end_date: str | None,
    update_watermark: bool,
) -> tuple[str, str, str | None, str | None, list[dict[str, Any]]]:
    source_key, env_var_name, _, ocds_url = _resolve_ocds_url_for_source(source)
    validated_start, validated_end = _validate_date_range(start_date, end_date)
    results = _get_and_classify_contracts(
        ocds_url=ocds_url,
        source_key=source_key,
        start_date=validated_start,
        end_date=validated_end,
        update_watermark=update_watermark,
    )
    return source_key, env_var_name, validated_start, validated_end, results


def _list_configured_sources() -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []

    suffix = "_OCDS_URL"
    for env_var, value in os.environ.items():
        if not env_var.endswith(suffix):
            continue
        if not str(value).strip():
            continue

        source_suffix = env_var[:-len(suffix)].strip()
        if not source_suffix:
            continue

        sources.append(
            {
                "source": source_suffix,
                "envVar": env_var,
            }
        )

    sources.sort(key=lambda item: item["source"])
    return sources


@ocds_blueprint.route(route="ocds/classify", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def classify_ocds_contracts(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("OCDS classify function started.")
    source_raw = req.params.get("source")
    start_date = req.params.get("start_date")
    end_date = req.params.get("end_date")

    try:
        source_key, env_var_name, schedule_env_var_name, _ = _resolve_ocds_url_for_source(source_raw)
        source_key, env_var_name, effective_start, effective_end, results = _run_ocds_classification_with_range(
            source=source_raw,
            start_date=start_date,
            end_date=end_date,
            update_watermark=not bool(start_date and end_date),
        )
        response_body = {
            "source": source_key,
            "ocdsUrlEnv": env_var_name,
            "checkScheduleEnv": schedule_env_var_name,
            "startDate": effective_start,
            "endDate": effective_end,
            "count": len(results),
            "items": results,
        }
        return func.HttpResponse(
            body=json.dumps(response_body, indent=2),
            status_code=200,
            mimetype="application/json",
        )
    except ValueError as exc:
        return func.HttpResponse(
            body=json.dumps({"type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}, indent=2),
            status_code=400,
            mimetype="application/json",
        )
    except Exception as exc:
        logging.exception("OCDS classify function failed")

        error_payload: dict[str, Any] = {
            "type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }

        resp = getattr(exc, "response", None)
        if resp is not None:
            req_obj = getattr(resp, "request", None)
            error_payload["downstreamStatus"] = getattr(resp, "status_code", None)
            error_payload["downstreamMethod"] = getattr(req_obj, "method", None)
            error_payload["downstreamUrl"] = getattr(req_obj, "url", None)
            error_payload["downstreamBody"] = (getattr(resp, "text", "") or "")[:1000]

        return func.HttpResponse(
            body=json.dumps(error_payload, indent=2),
            status_code=500,
            mimetype="application/json",
        )


@ocds_blueprint.route(route="ocds/runs", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def get_ocds_runs(req: func.HttpRequest) -> func.HttpResponse:
    limit_raw = (req.params.get("limit") or "20").strip()
    source_raw = req.params.get("source")
    try:
        source_key = _normalize_source_param(source_raw)
    except ValueError as exc:
        return func.HttpResponse(
            body=json.dumps({"type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}, indent=2),
            status_code=400,
            mimetype="application/json",
        )

    try:
        limit = int(limit_raw)
    except ValueError:
        return func.HttpResponse(
            body=json.dumps({"error": "Query parameter 'limit' must be an integer.", "traceback": traceback.format_exc()}),
            status_code=400,
            mimetype="application/json",
        )

    try:
        items = _get_recent_run_summaries(limit=limit, source_key=source_key)
        return func.HttpResponse(
            body=json.dumps({"count": len(items), "source": source_key, "items": items}, indent=2),
            status_code=200,
            mimetype="application/json",
        )
    except Exception as exc:
        logging.exception("Failed to retrieve OCDS run summaries")
        return func.HttpResponse(
            body=json.dumps({"type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}, indent=2),
            status_code=500,
            mimetype="application/json",
        )


@ocds_blueprint.route(route="ocds/sources", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def get_ocds_sources(req: func.HttpRequest) -> func.HttpResponse:
    try:
        source_raw = req.params.get("source")
        source_key, ocds_env_var_name, schedule_env_var_name = _resolve_source_env(source_raw)
        items = _list_configured_sources()

        selected = next((item for item in items if item.get("source") == source_key), None)
        if selected is None:
            selected = {
                "source": source_key,
                "envVar": ocds_env_var_name,
                "scheduleEnvVar": schedule_env_var_name,
                "isConfigured": False,
            }
        else:
            selected["scheduleEnvVar"] = schedule_env_var_name
            selected["isConfigured"] = True

        return func.HttpResponse(
            body=json.dumps({"count": len(items), "selected": selected, "items": items}, indent=2),
            status_code=200,
            mimetype="application/json",
        )
    except Exception as exc:
        logging.exception("Failed to list OCDS sources")
        return func.HttpResponse(
            body=json.dumps({"type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}, indent=2),
            status_code=500,
            mimetype="application/json",
        )
