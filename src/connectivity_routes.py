import json
import logging
import time
import traceback
from typing import Any

import azure.functions as func
from azure.identity import DefaultAzureCredential

from src.connectivity_checks import (
    _check_storage,
    _check_key_vault,
    _check_foundry_agent,
    _check_entra,
    _check_graph,
    _result,
)

connectivity_blueprint = func.Blueprint()


@connectivity_blueprint.route(route="connectivity", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
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
            checks.append(_result(name, False, {"error": str(exc), "traceback": traceback.format_exc()}, 0))

    try:
        entra_result, access_token = _check_entra(credential)
        checks.append(entra_result)
    except Exception as exc:
        checks.append(_result("entra", False, {"error": str(exc), "traceback": traceback.format_exc()}, 0))

    if access_token:
        try:
            checks.append(_check_graph(access_token))
        except Exception as exc:
            checks.append(_result("graphApi", False, {"error": str(exc), "traceback": traceback.format_exc()}, 0))
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
