"""Example: ADLS2 CSV roundtrip with env-configured connection.

This example shows how to configure ADLS via environment variables and run a
simple flow that:
- creates/ensures a container exists
- creates a folder inside the container
- mocks a CSV and writes it as a file
- reads the CSV back and prints the rows
- cleans up the created file and folder

Environment configuration (pick ONE of the following):

1) Connection string (recommended when available):
   export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__connection_string="<your-connection-string>"

   Or using the JSON overlay (high precedence, single var):
    export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__JSON='\
    {"connection_string":"<your-connection-string>"}'

2) Account URL + DefaultAzureCredential (for AAD-based auth):
   export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__account_url="https://<account>.dfs.core.windows.net"
   export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__use_default_credentials="true"

Optional tuning:
   export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__retries__attempts="5"
   export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__timeouts__connect_s="2.0"
   export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__timeouts__operation_s="30.0"

Run:
   python examples/adls_csv_flow.py
"""

from __future__ import annotations

import contextlib
import csv
import io
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from auto_workflow import flow, task
from auto_workflow.connectors import adls2

env = {"AUTO_WORKFLOW_CONNECTORS_ADLS2_ADLS_TEST__connection_string": "xxx"}

os.environ.update(env)


@dataclass(slots=True)
class CsvRecord:
    id: int
    name: str


# --- Tasks ---


@task
def ensure_container(container: str, profile: str) -> str:
    # Create the container (file system) if it doesn't exist
    # Best-effort: ignore if the container already exists or the SDK returns a benign error
    with adls2.client(profile=profile) as c, contextlib.suppress(Exception):
        c.create_container(container, exist_ok=True)
    return container


@task
def make_folder(container: str, folder: str, profile: str) -> str:
    with adls2.client(profile=profile) as c:
        c.make_dirs(container, folder, exist_ok=True)
    return folder


@task
def write_csv(container: str, folder: str, profile: str, filename: str = "sample.csv") -> str:
    # Mock a small CSV in-memory
    rows: list[CsvRecord] = [CsvRecord(1, "alice"), CsvRecord(2, "bob"), CsvRecord(3, "cathy")]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "name"])  # header
    for r in rows:
        w.writerow([r.id, r.name])
    data = buf.getvalue().encode("utf-8")

    path = f"{folder.rstrip('/')}/{filename}"
    with adls2.client(profile=profile) as c:
        c.upload_bytes(container, path, data, content_type="text/csv", overwrite=True)
    return path


@task
def read_csv(container: str, path: str, profile: str) -> list[list[str]]:
    with adls2.client(profile=profile) as c:
        data = c.download_bytes(container, path)
    text = data.decode("utf-8")
    out: list[list[str]] = []
    for row in csv.reader(io.StringIO(text)):
        out.append(row)
    return out


@task
def print_rows(rows: Iterable[Iterable[Any]]) -> None:
    print("CSV rows:")
    for row in rows:
        print(list(row))


@task
def cleanup(container: str, folder: str, path: str, profile: str) -> None:
    with adls2.client(profile=profile) as c:
        # Delete file first, then the folder
        with contextlib.suppress(Exception):
            c.delete_path(container, path)
        with contextlib.suppress(Exception):
            c.delete_path(container, folder, recursive=True)


# --- Flow ---


@flow
def adls_csv_flow(
    container: str = "demo-container",
    folder_prefix: str = "incoming",
    profile: str = "adls_test",
):
    # Timestamped folder for a tidy run
    folder = f"{folder_prefix}/{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"

    ensured = ensure_container(container, profile)
    made = make_folder(ensured, folder, profile)
    file_path = write_csv(ensured, made, profile)
    rows = read_csv(ensured, file_path, profile)
    # Print before cleanup; ensure ordering by chaining
    print_rows(rows)
    cleanup(ensured, made, file_path, profile)
    return rows


if __name__ == "__main__":
    result = adls_csv_flow.run()
    # Printed via print_rows task; also return rows here for convenience
    print("Flow returned", len(result), "rows")
