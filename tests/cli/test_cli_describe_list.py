import json
import os
import pathlib
import subprocess
import sys
import textwrap

from auto_workflow import flow, task


@task
def one():
    return 1


@task
def two(x):
    return x + 1


@flow
def cli_flow():
    a = one()
    b = two(a)
    return b


def test_cli_describe(tmp_path):
    # write a temporary module file
    mod = tmp_path / "mymod.py"
    mod.write_text(
        textwrap.dedent("""\
from auto_workflow import task, flow
@task
def one(): return 1
@task
def two(x): return x+1
@flow
def cli_flow():
    a = one(); b = two(a); return b
""")
    )
    _ = os.environ.copy()  # ignore copy
    cmd = [sys.executable, "-m", "auto_workflow.cli", "describe", f"{mod.stem}:cli_flow"]
    proc = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["count"] == 2
    assert any(n["task"] == "one" for n in data["nodes"])


def test_cli_list(tmp_path):
    mod = tmp_path / "mymod.py"
    mod.write_text(
        "from auto_workflow import task, flow\n@task\ndef t(): return 1\n@flow\ndef f(): return t()"
    )
    cmd = [sys.executable, "-m", "auto_workflow.cli", "list", f"{mod.stem}"]
    proc = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert "f" in data and data["f"] == 1


def test_cli_list_empty_module(tmp_path):
    mod = tmp_path / "empty.py"
    mod.write_text("x=1\n")
    cmd = [sys.executable, "-m", "auto_workflow.cli", "list", f"{mod.stem}"]
    proc = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data == {}
