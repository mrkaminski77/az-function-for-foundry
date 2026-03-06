import logging
import os
from typing import Any

from src.ews_sender import send_results_via_ews
from src.graph_sender import send_results_via_graph


def _resolve_provider() -> str:
    return os.getenv("RESULTS_SENDER_PROVIDER", "ews").strip().lower()


def send_classification_results(source_key: str, results: list[dict[str, Any]]) -> None:
    provider = _resolve_provider()

    if provider == "none":
        logging.info("Result sending disabled. provider=none")
        return

    if provider == "ews":
        send_results_via_ews(source_key=source_key, results=results)
        return

    if provider == "graph":
        send_results_via_graph(source_key=source_key, results=results)
        return

    raise ValueError(
        "Invalid RESULTS_SENDER_PROVIDER value. Supported values are: ews, graph, none"
    )
