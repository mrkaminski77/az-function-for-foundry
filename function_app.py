import json
import logging
import os
import time
from typing import Any
from azure.identity import DefaultAzureCredential

import azure.functions as func
from src.austender import _get_and_classify_contracts
from src.connectivitychecks import (
    _check_storage,
    _check_key_vault,
    _check_foundry_agent,
    _check_entra,
    _check_graph,
)

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="austender/classify", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def classify_austender_contracts(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("AusTender classify function started.")

    ocds_url = os.getenv("AUSTENDER_OCDS_URL", "").strip()
    if not ocds_url:
        return func.HttpResponse(
            body=json.dumps({"error": "Missing required environment variable 'AUSTENDER_OCDS_URL'"}),
            status_code=500,
            mimetype="application/json",
        )

    try:
        results = _get_and_classify_contracts(ocds_url=ocds_url)
        response_body = {
            "count": len(results),
            "items": results,
        }
        return func.HttpResponse(
            body=json.dumps(response_body, indent=2),
            status_code=200,
            mimetype="application/json",
        )
    except Exception as exc:
        logging.exception("AusTender classify function failed")
        return func.HttpResponse(
            body=json.dumps({"error": str(exc)}),
            status_code=500,
            mimetype="application/json",
        )

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
