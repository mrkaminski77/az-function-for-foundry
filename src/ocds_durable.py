import json
import logging
import traceback
from typing import Any

import azure.durable_functions as df
import azure.functions as func

from src.ocds_pipeline import _get_and_classify_contracts
from src.ocds_routes import _resolve_ocds_url_for_source, _validate_date_range

ocds_durable_blueprint = df.Blueprint()


@ocds_durable_blueprint.route(route="ocds/classify-range", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
@ocds_durable_blueprint.durable_client_input(client_name="client")
async def classify_range_start(req: func.HttpRequest, client) -> func.HttpResponse:
    logging.info("OCDS classify-range durable start triggered.")
    source_raw = req.params.get("source")
    start_date = req.params.get("start_date")
    end_date = req.params.get("end_date")

    try:
        _resolve_ocds_url_for_source(source_raw)
        validated_start, validated_end = _validate_date_range(start_date, end_date)
        if not validated_start or not validated_end:
            raise ValueError("Query parameters 'start_date' and 'end_date' are required for this route.")
    except ValueError as exc:
        return func.HttpResponse(
            body=json.dumps({"type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}, indent=2),
            status_code=400,
            mimetype="application/json",
        )

    payload = {
        "source": source_raw,
        "start_date": validated_start,
        "end_date": validated_end,
    }

    try:
        instance_id = await client.start_new("classify_range_orchestrator", client_input=payload)
    except Exception as exc:
        logging.exception("Failed to start durable orchestration")
        return func.HttpResponse(
            body=json.dumps({"type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}, indent=2),
            status_code=500,
            mimetype="application/json",
        )

    logging.info("Started orchestration with instance id: %s", instance_id)

    return func.HttpResponse(
        body=json.dumps({"job_id": instance_id, "status": "accepted"}, indent=2),
        status_code=202,
        mimetype="application/json",
    )


@ocds_durable_blueprint.orchestration_trigger(context_name="context")
def classify_range_orchestrator(context: df.DurableOrchestrationContext):
    params = context.get_input()
    result = yield context.call_activity("classify_range_activity", params)
    return result


@ocds_durable_blueprint.activity_trigger(input_name="params")
def classify_range_activity(params: dict) -> dict:
    source_raw = params.get("source")
    start_date = params.get("start_date")
    end_date = params.get("end_date")

    source_key, env_var_name, schedule_env_var_name, ocds_url = _resolve_ocds_url_for_source(source_raw)

    results = _get_and_classify_contracts(
        ocds_url=ocds_url,
        source_key=source_key,
        start_date=start_date,
        end_date=end_date,
        update_watermark=False,
    )

    return {
        "source": source_key,
        "ocdsUrlEnv": env_var_name,
        "checkScheduleEnv": schedule_env_var_name,
        "startDate": start_date,
        "endDate": end_date,
        "watermarkUpdated": False,
        "count": len(results),
        "items": results,
    }


@ocds_durable_blueprint.route(route="ocds/classify-range/status/{job_id}", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
@ocds_durable_blueprint.durable_client_input(client_name="client")
async def classify_range_status(req: func.HttpRequest, client) -> func.HttpResponse:
    job_id = req.route_params.get("job_id", "").strip()

    if not job_id:
        return func.HttpResponse(
            body=json.dumps({"error": "job_id is required"}, indent=2),
            status_code=400,
            mimetype="application/json",
        )

    try:
        status = await client.get_status(job_id)

        if status is None:
            return func.HttpResponse(
                body=json.dumps({"error": f"No orchestration found with job_id '{job_id}'"}, indent=2),
                status_code=404,
                mimetype="application/json",
            )

        runtime_status = (
            status.runtime_status.value
            if hasattr(status.runtime_status, "value")
            else str(status.runtime_status)
        )

        response: dict[str, Any] = {
            "job_id": job_id,
            "status": runtime_status,
            "created_time": status.created_time.isoformat() if status.created_time else None,
            "last_updated_time": status.last_updated_time.isoformat() if status.last_updated_time else None,
        }

        if runtime_status == "Completed":
            response["output"] = status.output
        elif runtime_status == "Failed":
            response["error"] = str(status.output)

        return func.HttpResponse(
            body=json.dumps(response, indent=2),
            status_code=200,
            mimetype="application/json",
        )
    except Exception as exc:
        logging.exception("Failed to retrieve orchestration status")
        return func.HttpResponse(
            body=json.dumps({"type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}, indent=2),
            status_code=500,
            mimetype="application/json",
        )
