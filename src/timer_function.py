import logging
import os

import azure.functions as func

from src.ocds_pipeline import _get_and_classify_contracts
from src.result_sender import send_classification_results

timer_blueprint = func.Blueprint()


def _run_endpoint_classification(
    timer: func.TimerRequest,
    endpoint_name: str,
) -> None:
    if timer.past_due:
        logging.warning("%s timer trigger is running later than scheduled.", endpoint_name)

    source_key = endpoint_name.strip().upper()
    ocds_url_env_var = f"{source_key}_OCDS_URL"
    ocds_url = os.getenv(ocds_url_env_var, "").strip()
    if not ocds_url:
        raise ValueError(f"Missing required environment variable '{ocds_url_env_var}'")

    logging.info(
        "%s scheduled orchestration started. endpointEnvVar=%s",
        endpoint_name,
        ocds_url_env_var,
    )
    try:
        results = _get_and_classify_contracts(ocds_url=ocds_url, source_key=source_key)
        send_classification_results(source_key=source_key, results=results)
        logging.info(
            "%s scheduled orchestration completed. endpointEnvVar=%s processed=%d",
            endpoint_name,
            ocds_url_env_var,
            len(results),
        )
    except Exception:
        logging.exception(
            "%s scheduled orchestration failed. endpointEnvVar=%s",
            endpoint_name,
            ocds_url_env_var,
        )
        raise


@timer_blueprint.timer_trigger(
    schedule="%AUSTENDER_CHECK_SCHEDULE%",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def orchestrate_austender(timer: func.TimerRequest) -> None:
    _run_endpoint_classification(
        timer=timer,
        endpoint_name="AUSTENDER",
    )


# Pattern for future endpoint timers:
# 1) Add env vars, e.g. MYENDPOINT_OCDS_URL and MYENDPOINT_CHECK_SCHEDULE.
# 2) Copy this trigger and change `schedule`, `ocds_url_env_var`, and `endpoint_name`.
