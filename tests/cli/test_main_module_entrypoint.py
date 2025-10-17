import runpy


def test_main_module_imports_without_executing_cli():
    # Import the __main__ module but do not execute the CLI path.
    # Using a non-"__main__" run_name avoids invoking SystemExit from argument parsing.
    runpy.run_module("auto_workflow.__main__", run_name="pkg")
