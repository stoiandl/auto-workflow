"""Pluggable metrics provider abstraction."""

from __future__ import annotations

from typing import Any, Protocol


class MetricsProvider(Protocol):  # pragma: no cover - interface
    def inc(self, name: str, value: float = 1.0, **labels: Any) -> None: ...
    def observe(self, name: str, value: float, **labels: Any) -> None: ...


class InMemoryMetrics(MetricsProvider):
    def __init__(self) -> None:
        self.counters: dict[str, float] = {}
        self.histograms: dict[str, list[float]] = {}

    def inc(self, name: str, value: float = 1.0, **labels: Any) -> None:
        key = name
        self.counters[key] = self.counters.get(key, 0.0) + value

    def observe(self, name: str, value: float, **labels: Any) -> None:
        self.histograms.setdefault(name, []).append(value)


_provider: MetricsProvider = InMemoryMetrics()


def set_metrics_provider(p: MetricsProvider) -> None:
    global _provider
    _provider = p


def get_metrics_provider() -> MetricsProvider:
    return _provider
