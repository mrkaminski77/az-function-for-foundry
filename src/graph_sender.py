import logging
import os
from typing import Any


def _is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def send_results_via_graph(source_key: str, results: list[dict[str, Any]]) -> None:
    if not _is_truthy(os.getenv("GRAPH_SEND_RESULTS_ENABLED", "false")):
        logging.info(
            "Graph sending disabled. Set GRAPH_SEND_RESULTS_ENABLED=true when Graph implementation is ready."
        )
        return

    raise NotImplementedError(
        "Graph sender is scaffolded but not implemented yet. "
        "Use RESULTS_SENDER_PROVIDER=ews for now."
    )
