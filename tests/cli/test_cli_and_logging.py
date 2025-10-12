import json
import os
import sys
import types

from auto_workflow import flow, task
from auto_workflow.cli import main


@task
def base():
    return 2


@task
def add_one(x: int):
    return x + 1


@flow
def cli_flow():
    return add_one(base())


# Expose flow in a dynamic module for loader
module_name = "tmp_cli_flows"
mod = types.ModuleType(module_name)
mod.cli_flow = cli_flow
sys.modules[module_name] = mod


def test_cli_run_and_describe(capsys):
    # run
    rc = main(["run", f"{module_name}:cli_flow"])  # no params
    assert rc == 0
    capsys.readouterr()  # discard run output
    # describe
    rc = main(["describe", f"{module_name}:cli_flow"])
    assert rc == 0
    out = capsys.readouterr().out
    desc = json.loads(out)
    assert desc["flow"] == "cli_flow"


def test_cli_run_with_params_and_structured_logs(capsys, monkeypatch):
    # Ensure structured logging path executes
    rc = main(
        [
            "run",
            f"{module_name}:cli_flow",
            "--structured-logs",
            "--failure-policy",
            "fail_fast",
            "--max-concurrency",
            "4",
            "--params",
            json.dumps({}),
        ]
    )
    assert rc == 0
