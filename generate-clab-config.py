#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
import importlib.util


def _load_parser():
    parser_file = Path.cwd() / "clabgen" / "parse-solver-json.py"

    spec = importlib.util.spec_from_file_location("clabgen.parse_solver_json", parser_file)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> None:
    if len(sys.argv) < 4:
        print("usage: generate-clab-config.py <solver.json> <output.yml> <output-bridges.nix>")
        raise SystemExit(1)

    solver_json = sys.argv[1]
    topology_out = sys.argv[2]
    bridges_out = sys.argv[3]

    parser = _load_parser()
    parser.write_outputs(solver_json, topology_out, bridges_out)


if __name__ == "__main__":
    main()
