#!/usr/bin/env python3

import sys
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from clabgen.parser import parse_solver
from clabgen.generator import generate_topology


def main():
    if len(sys.argv) < 4:
        print("usage: generate-clab-config.py <solver.json> <output.yml> <bridges.nix>")
        sys.exit(1)

    solver_path = sys.argv[1]
    output_path = sys.argv[2]
    bridges_path = sys.argv[3]

    sites = parse_solver(solver_path)

    merged_nodes = {}
    merged_links = []
    merged_bridges = set()

    for site in sites.values():
        topo = generate_topology(site)

        merged_nodes.update(topo["topology"]["nodes"])
        merged_links.extend(topo["topology"]["links"])
        merged_bridges.update(topo["bridges"])

    final_topology = {
        "name": "fabric",
        "topology": {
            "defaults": {
                "kind": "linux",
                "image": "frrouting/frr:latest",
                "network-mode": "none",
            },
            "nodes": merged_nodes,
            "links": merged_links,
        },
    }

    with open(output_path, "w") as f:
        yaml.dump(final_topology, f, sort_keys=False)

    with open(bridges_path, "w") as f:
        f.write("{ lib, ... }:\n{\n  bridges = [\n")
        for b in sorted(merged_bridges):
            f.write(f'    "{b}"\n')
        f.write("  ];\n}\n")


if __name__ == "__main__":
    main()
