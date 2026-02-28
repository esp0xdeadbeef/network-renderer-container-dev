# ./generate-vm-bridges.py
#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import List, Set

DEFAULT_SOLVER_JSON = "output-network-solver.json"
OUTPUT_FILE = "bridges-generated.nix"
MAX_LEN = 15


def short_name(seed: str) -> str:
    h = hashlib.sha1(seed.encode()).hexdigest()[:10]
    name = f"br{h}"
    return name[:MAX_LEN]


def main() -> None:
    solver_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_SOLVER_JSON)
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(OUTPUT_FILE)

    data = json.loads(solver_path.read_text())

    bridges: Set[str] = set()

    enterprises = data.get("enterprises", {})
    for ent_name, ent_obj in enterprises.items():
        sites = ent_obj.get("sites", {})
        for site_name, site_obj in sites.items():
            links = site_obj.get("links", {})
            for link_key, link_obj in links.items():
                if (
                    isinstance(link_obj, dict)
                    and link_obj.get("kind") == "p2p"
                    and isinstance(link_obj.get("endpoints"), dict)
                    and len(link_obj["endpoints"]) == 2
                ):
                    seed = f"{ent_name}-{site_name}-{link_key}"
                    bridges.add(short_name(seed))

    bridge_list: List[str] = sorted(bridges)

    lines: List[str] = []
    lines.append("{ lib, ... }:")
    lines.append("{")
    lines.append("  bridges = [")
    for b in bridge_list:
        lines.append(f'    "{b}"')
    lines.append("  ];")
    lines.append("}")

    output_path.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
