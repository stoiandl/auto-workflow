import json
import sys
import types

from auto_workflow import flow, task
from auto_workflow.cli import main


@task
def t():
    return 1


@flow
def f():
    return t()


def test_cli_list_inprocess(capsys):
    # Create ephemeral module exposing a flow for the CLI list command
    module_name = "tmp_cli_list_mod"
    mod = types.ModuleType(module_name)
    mod.f = f
    sys.modules[module_name] = mod

    rc = main(["list", module_name])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data == {"f": 1}
