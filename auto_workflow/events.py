"""Lightweight event bus."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

_subscribers: dict[str, list[Callable[[dict[str, Any]], None]]] = {}
logger = logging.getLogger("auto_workflow.events")


def subscribe(event: str, callback: Callable[[dict[str, Any]], None]) -> None:
    _subscribers.setdefault(event, []).append(callback)


def emit(event: str, payload: dict[str, Any]) -> None:
    for cb in _subscribers.get(event, []):
        try:
            cb(payload)
        except Exception as e:  # pragma: no cover
            logger.debug("event subscriber error", exc_info=e)
