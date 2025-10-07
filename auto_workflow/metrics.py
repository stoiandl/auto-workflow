"""Lightweight metrics facade (no-op by default)."""

from __future__ import annotations

from typing import Any

_counters: dict[str, float] = {}
_histograms: dict[str, list[float]] = {}


def inc(name: str, value: float = 1.0) -> None:
    _counters[name] = _counters.get(name, 0.0) + value


def observe(name: str, value: float) -> None:
    _histograms.setdefault(name, []).append(value)


def snapshot() -> dict[str, Any]:  # pragma: no cover - debug helper
    return {"counters": dict(_counters), "histograms": {k: list(v) for k, v in _histograms.items()}}
