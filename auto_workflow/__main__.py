"""Module entry point for `python -m auto_workflow`.

Delegates to the package CLI defined in `auto_workflow.cli`.
"""
from .cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
