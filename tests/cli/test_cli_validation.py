import json
import subprocess
import sys


def test_cli_run_rejects_nonpositive_max_concurrency(tmp_path):
    # minimal module with a trivial flow
    mod = tmp_path / "m.py"
    mod.write_text(
        "from auto_workflow import task, flow\n"
        "@task\n"
        "def t(): return 1\n"
        "@flow\n"
        "def f(): return t()\n"
    )
    cmd = [
        sys.executable,
        "-m",
        "auto_workflow.cli",
        "run",
        f"{mod.stem}:f",
        "--max-concurrency",
        "0",
    ]
    proc = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "max-concurrency" in proc.stderr


def test_cli_run_failure_policy_choices(tmp_path):
    mod = tmp_path / "m2.py"
    mod.write_text(
        "from auto_workflow import task, flow\n"
        "@task\n"
        "def t(): return 1\n"
        "@flow\n"
        "def f(): return t()\n"
    )
    # Valid choice should pass
    ok = subprocess.run(
        [
            sys.executable,
            "-m",
            "auto_workflow.cli",
            "run",
            f"{mod.stem}:f",
            "--failure-policy",
            "continue",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert ok.returncode == 0
