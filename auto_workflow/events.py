"""Lightweight event bus."""
from __future__ import annotations
from typing import Callable, Dict, List, Any
import logging

_subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
logger = logging.getLogger("auto_workflow.events")

def subscribe(event: str, callback: Callable[[Dict[str, Any]], None]) -> None:
    _subscribers.setdefault(event, []).append(callback)

def emit(event: str, payload: Dict[str, Any]) -> None:
    for cb in _subscribers.get(event, []):
        try:
            cb(payload)
        except Exception as e:  # pragma: no cover
            logger.debug("event subscriber error", exc_info=e)
