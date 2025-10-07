"""CLI entry points."""

from __future__ import annotations

import argparse
import importlib
import json

from .logging_middleware import structured_logging_middleware
from .middleware import register


def load_flow(dotted: str):
    if ":" not in dotted:
        raise SystemExit("Flow path must be module:object")
    mod_name, attr = dotted.split(":", 1)
    mod = importlib.import_module(mod_name)
    flow_obj = getattr(mod, attr)
    return flow_obj


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser("auto-workflow")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="Run a flow")
    run_p.add_argument("flow", help="module:flow_object path")
    run_p.add_argument("--executor", default="async")
    run_p.add_argument("--failure-policy", default="fail_fast")
    run_p.add_argument("--max-concurrency", type=int, default=None)
    run_p.add_argument("--params", help="JSON params dict", default=None)
    run_p.add_argument("--structured-logs", action="store_true")

    desc_p = sub.add_parser("describe", help="Describe a flow DAG")
    desc_p.add_argument("flow", help="module:flow_object path")
    desc_p.add_argument("--params", help="JSON params dict", default=None)

    list_p = sub.add_parser("list", help="List flows in a module")
    list_p.add_argument("module", help="Python module to scan for Flow objects")

    ns = parser.parse_args(argv)
    if ns.cmd == "run":
        if ns.structured_logs:
            register(structured_logging_middleware)
        params = json.loads(ns.params) if ns.params else None
        flow_obj = load_flow(ns.flow)
        result = flow_obj.run(
            executor=ns.executor,
            failure_policy=ns.failure_policy,
            max_concurrency=ns.max_concurrency,
            params=params,
        )
        print(result)
        return 0
    if ns.cmd == "describe":
        flow_obj = load_flow(ns.flow)
        params = json.loads(ns.params) if ns.params else None
        desc = flow_obj.describe(params=params) if params else flow_obj.describe()
        print(json.dumps(desc, indent=2))
        return 0
    if ns.cmd == "list":
        mod = importlib.import_module(ns.module)
        out = {}
        for name, obj in vars(mod).items():
            from auto_workflow.flow import Flow

            if isinstance(obj, Flow):
                out[name] = obj.describe()["count"]
        print(json.dumps(out, indent=2))
        return 0
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
