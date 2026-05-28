"""
Author: L. Saetta
Date Last Modified: 2026-05-28
License: MIT
Description:    Minimal structured logging helpers for orchestration.
"""

from __future__ import annotations

import json
import logging
from typing import Any

LOGGER_NAME = "procurement_orchestrator"


def configure_logging() -> None:
    """Configure minimal process logging when no handlers exist."""

    logging.basicConfig(level=logging.INFO, format="%(message)s")


def log_step(
    logger: logging.Logger,
    *,
    orchestration_id: str,
    request_id: str,
    event_type: str,
    message: str,
    **payload: Any,
) -> None:
    """Write one JSON log line for an orchestration step."""

    logger.info(
        json.dumps(
            {
                "component": LOGGER_NAME,
                "orchestration_id": orchestration_id,
                "request_id": request_id,
                "event_type": event_type,
                "message": message,
                "payload": payload,
            },
            ensure_ascii=False,
            default=str,
        )
    )
