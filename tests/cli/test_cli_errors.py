import subprocess
import sys


def test_cli_describe_invalid_module(tmp_path):
    cmd = [sys.executable, "-m", "auto_workflow.cli", "describe", "no_such_mod:obj"]
    proc = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "Failed to import module" in proc.stderr


def test_cli_describe_missing_object(tmp_path):
    mod = tmp_path / "m.py"
    mod.write_text("x=1\n")
    cmd = [sys.executable, "-m", "auto_workflow.cli", "describe", f"{mod.stem}:nope"]
    proc = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "not found in module" in proc.stderr


def test_cli_list_invalid_module(tmp_path):
    cmd = [sys.executable, "-m", "auto_workflow.cli", "list", "no_such_mod"]
    proc = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "Failed to import module" in proc.stderr
