"""Global pytest configuration to ensure local services are up before tests.

This starts the docker-compose stack in test_helpers/ when running tests locally,
waits for Postgres to be available, and configures the DSN env so integration
tests can run. In CI, we also use this mechanism.
"""

import os
import subprocess
import sys
import time
from collections.abc import Generator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPERS = ROOT / "test_helpers"
COMPOSE_FILE = HELPERS / "docker-compose.yml"
WAIT_SCRIPT = HELPERS / "wait-for-postgres.sh"


def _run(cmd: list[str], env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, cwd=str(ROOT), env=env or os.environ.copy())


def _ensure_executable(p: Path) -> None:
    try:
        mode = p.stat().st_mode
        p.chmod(mode | 0o111)
    except FileNotFoundError:
        pass


@pytest.fixture(scope="session", autouse=True)
def _compose_services_session() -> Generator[None, None, None]:
    # Allow opting out (e.g., if running against external DB)
    if os.getenv("AW_NO_DOCKER"):
        return
    # If DSN already provided, don't start local services
    if os.getenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_EXAMPLE__DSN"):
        return


_COMPOSE_STARTED = False


def pytest_sessionstart(session: pytest.Session) -> None:  # pragma: no cover - env/setup
    global _COMPOSE_STARTED
    # Allow opting out (e.g., if running against external DB)
    if os.getenv("AW_NO_DOCKER"):
        return
    # If DSN already provided, don't start local services
    if os.getenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_EXAMPLE__DSN"):
        return

    # Spin up compose services before collection so env-gated skips see DSN
    if COMPOSE_FILE.exists():
        try:
            _run(["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"])
            _COMPOSE_STARTED = True
        except Exception as e:
            print(f"WARNING: docker compose up failed: {e}", file=sys.stderr)
            return
    else:
        print("WARNING: compose file missing, skipping docker compose up", file=sys.stderr)
        return

    # Wait for Postgres and export DSN
    _ensure_executable(WAIT_SCRIPT)
    host = os.getenv("AW_PG_HOST", "127.0.0.1")
    port = os.getenv("AW_PG_PORT", "5432")
    try:
        # small grace period after compose up to avoid transient warnings
        time.sleep(5)
        _run([str(WAIT_SCRIPT), host, port])
        # assign directly so skip markers see it in this process
        os.environ["AUTO_WORKFLOW_CONNECTORS_POSTGRES_EXAMPLE__DSN"] = (
            f"postgresql://postgres:postgres@{host}:{port}/postgres"
        )
    except Exception as e:
        print(f"WARNING: wait-for-postgres failed: {e}", file=sys.stderr)


def pytest_sessionfinish(
    session: pytest.Session, exitstatus: int
) -> None:  # pragma: no cover - teardown
    if _COMPOSE_STARTED and not os.getenv("AW_KEEP_DOCKER"):
        try:
            # small grace period before tearing down the stack to avoid noisy warnings
            time.sleep(5)
            _run(["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"])
        except Exception as e:
            print(f"WARNING: docker compose down failed: {e}", file=sys.stderr)
