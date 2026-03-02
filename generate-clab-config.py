#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from clabgen.export import write_outputs


def main() -> None:
    if len(sys.argv) < 4:
        print("usage: generate-clab-config.py <solver.json> <output.yml> <output-bridges.nix>")
        raise SystemExit(1)

    solver_json = sys.argv[1]
    topology_out = sys.argv[2]
    bridges_out = sys.argv[3]

    write_outputs(solver_json, topology_out, bridges_out)


if __name__ == "__main__":
    main()
