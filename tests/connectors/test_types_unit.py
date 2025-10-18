from __future__ import annotations

from auto_workflow.connectors.types import (
    ADLS2Config,
    PostgresConfig,
    PostgresPoolConfig,
    RetryConfig,
    S3Config,
    S3Credentials,
    TimeoutConfig,
    to_dict,
)


def test_dataclass_defaults_and_to_dict():
    # Postgres
    pg = PostgresConfig()
    d = to_dict(pg)
    assert d["port"] == 5432
    assert d["sslmode"] == "require"
    assert isinstance(d["pool"], dict) and d["pool"]["min_size"] == 1
    # Retry/timeouts defaults nested
    assert d["retries"]["attempts"] == 3
    assert d["timeouts"]["operation_s"] == 60.0

    # S3
    s3 = S3Config(credentials=S3Credentials(access_key_id="AKIA", secret_access_key="x"))
    sd = to_dict(s3)
    assert sd["retries"]["attempts"] == 5
    assert sd["credentials"]["access_key_id"] == "AKIA"

    # ADLS2
    az = ADLS2Config()
    azd = to_dict(az)
    assert azd["use_default_credentials"] is True

    # Pool config standalone
    pc = PostgresPoolConfig(min_size=2, max_size=20)
    pcd = to_dict(pc)
    assert pcd["min_size"] == 2 and pcd["max_size"] == 20

    # Retry/Timeout standalone
    rc = RetryConfig(attempts=7, jitter=False)
    rcd = to_dict(rc)
    assert rcd["attempts"] == 7 and rcd["jitter"] is False

    tc = TimeoutConfig(connect_s=1.5, operation_s=3.0)
    tcd = to_dict(tc)
    assert tcd["connect_s"] == 1.5 and tcd["operation_s"] == 3.0
