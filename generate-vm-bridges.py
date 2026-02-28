# ./generate-vm-bridges.py
#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

DEFAULT_SOLVER_JSON = "output-network-solver.json"
OUTPUT_FILE = "vm-bridges-generated.nix"


def main() -> None:
    _ = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_SOLVER_JSON)
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(OUTPUT_FILE)

    output_path.write_text(
        "{ lib, ... }:\n{\n  bridges = [ ];\n}\n"
    )


if __name__ == "__main__":
    main()
