"""Typed configs and simple protocols used by connectors (scaffolding)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RetryConfig:
    attempts: int = 3
    backoff_min_ms: int = 100
    backoff_max_ms: int = 2000
    jitter: bool = True


@dataclass(slots=True)
class TimeoutConfig:
    connect_s: float | None = 5.0
    operation_s: float | None = 60.0


@dataclass(slots=True)
class PostgresPoolConfig:
    min_size: int = 1
    max_size: int = 10
    max_idle_s: int = 300


@dataclass(slots=True)
class PostgresConfig:
    dsn: str | None = None
    host: str | None = None
    port: int | None = 5432
    database: str | None = None
    user: str | None = None
    password: str | None = None
    sslmode: str | None = "require"
    statement_timeout_ms: int | None = 30000
    pool: PostgresPoolConfig = PostgresPoolConfig()
    retries: RetryConfig = RetryConfig()
    timeouts: TimeoutConfig = TimeoutConfig()


@dataclass(slots=True)
class S3Credentials:
    access_key_id: str | None = None
    secret_access_key: str | None = None
    session_token: str | None = None


@dataclass(slots=True)
class S3Config:
    region: str | None = None
    endpoint_url: str | None = None
    use_default_credentials: bool = True
    sse: str | None = None
    retries: RetryConfig = RetryConfig(attempts=5)
    timeouts: TimeoutConfig = TimeoutConfig(connect_s=5.0, operation_s=120.0)
    addressing_style: str = "auto"
    credentials: S3Credentials | None = None


@dataclass(slots=True)
class ADLS2Config:
    account_url: str | None = None
    use_default_credentials: bool = True
    credential: str | None = None  # SAS or key or client secret reference
    retries: RetryConfig = RetryConfig(attempts=5)
    timeouts: TimeoutConfig = TimeoutConfig(connect_s=5.0, operation_s=60.0)


def to_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "__dict__"):
        # dataclasses with slots still provide asdict-like through __dict__ for simple cases
        return {k: to_dict(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, (list, tuple)):
        return [to_dict(x) for x in obj]
    return obj
