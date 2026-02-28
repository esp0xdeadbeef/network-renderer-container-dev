# ./generate-clab-config.py
#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path.cwd()))

import yaml  # type: ignore

from clabgen.solver import (
    load_solver,
    extract_enterprise_sites,
    validate_site_invariants,
    validate_routing_assumptions,
    fail,
)

DEFAULT_SOLVER_JSON = "output-network-solver.json"
DEFAULT_TOPO_FILE = "fabric.clab.yml"
IMAGE = "frrouting/frr:latest"


def _emit_iface_routes(iface_obj: Dict[str, Any], version: int, dev: str) -> List[str]:
    key = f"routes{version}"
    routes = iface_obj.get(key, [])
    if not isinstance(routes, list):
        return []

    cmds: List[str] = []
    for r in routes:
        if not isinstance(r, dict):
            continue
        dst = r.get("dst")
        if not isinstance(dst, str) or not dst:
            continue
        if version == 4:
            via = r.get("via4")
            if not isinstance(via, str) or not via:
                continue
            cmds.append(f"ip route replace {dst} via {via} dev {dev}")
        else:
            via = r.get("via6")
            if not isinstance(via, str) or not via:
                continue
            cmds.append(f"ip -6 route replace {dst} via {via} dev {dev}")
    return cmds


def _render_node(
    ent: str,
    site: str,
    node_name: str,
    node_obj: Dict[str, Any],
    p2p_links: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    full_name = f"{ent}-{site}-{node_name}"
    exec_cmds: List[str] = [
        "sysctl -w net.ipv4.ip_forward=1",
        "sysctl -w net.ipv6.conf.all.forwarding=1",
    ]

    eth_idx = 1
    interfaces = node_obj.get("interfaces", {})
    if not isinstance(interfaces, dict):
        return {"exec": exec_cmds}

    for link_key, link_obj in p2p_links.items():
        if node_name not in link_obj["endpoints"]:
            continue

        iface_obj = interfaces.get(link_key)
        if not isinstance(iface_obj, dict):
            continue

        dev = f"eth{eth_idx}"
        exec_cmds.append(f"ip link set {dev} up")

        addr4 = iface_obj.get("addr4")
        addr6 = iface_obj.get("addr6")

        if isinstance(addr4, str) and addr4:
            exec_cmds.append(f"ip addr replace {addr4} dev {dev}")
        if isinstance(addr6, str) and addr6:
            exec_cmds.append(f"ip -6 addr replace {addr6} dev {dev}")

        exec_cmds.extend(_emit_iface_routes(iface_obj, 4, dev))
        exec_cmds.extend(_emit_iface_routes(iface_obj, 6, dev))

        eth_idx += 1

    return {"exec": exec_cmds}


def main() -> None:
    solver_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_SOLVER_JSON)
    topo_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(DEFAULT_TOPO_FILE)

    data = load_solver(solver_path)
    sites = extract_enterprise_sites(data)

    rendered_nodes: Dict[str, Any] = {}
    rendered_links: List[Dict[str, Any]] = []

    for ent_name, site_name, site in sites:
        site_ctx = {"enterprise": ent_name, "site": site_name, "siteObj": site}

        validate_site_invariants(site, context=site_ctx)
        validate_routing_assumptions(site, context=site_ctx)

        nodes = site.get("nodes", {})
        links = site.get("links", {})

        if not isinstance(nodes, dict) or not isinstance(links, dict):
            fail("Invalid solver structure: nodes/links missing", context=site_ctx)

        # Strict 2-endpoint p2p links only
        p2p_links = {
            lk: lo
            for lk, lo in links.items()
            if isinstance(lo, dict)
            and lo.get("kind") == "p2p"
            and isinstance(lo.get("endpoints"), dict)
            and len(lo["endpoints"]) == 2
        }

        # Render ALL original nodes exactly once
        for node_name, node_obj in nodes.items():
            if not isinstance(node_obj, dict):
                continue
            rendered_nodes[f"{ent_name}-{site_name}-{node_name}"] = _render_node(
                ent_name, site_name, node_name, node_obj, p2p_links
            )

        # Render ALL strict p2p links exactly once
        for link_key, link_obj in p2p_links.items():
            eps = link_obj["endpoints"]
            a, b = list(eps.keys())

            # determine eth index by order of appearance in node rendering
            def eth_index(node: str) -> int:
                idx = 1
                for lk2, lo2 in p2p_links.items():
                    if node in lo2["endpoints"]:
                        if lk2 == link_key:
                            return idx
                        idx += 1
                return 1

            rendered_links.append(
                {
                    "endpoints": [
                        f"{ent_name}-{site_name}-{a}:eth{eth_index(a)}",
                        f"{ent_name}-{site_name}-{b}:eth{eth_index(b)}",
                    ]
                }
            )

    topology = {
        "name": "fabric",
        "topology": {
            "defaults": {
                "kind": "linux",
                "image": IMAGE,
                "network-mode": "none",
                "sysctls": {
                    "net.ipv4.ip_forward": "1",
                    "net.ipv6.conf.all.forwarding": "1",
                    "net.ipv4.conf.default.rp_filter": "0",
                },
            },
            "nodes": rendered_nodes,
            "links": rendered_links,
        },
    }

    with topo_path.open("w") as f:
        yaml.dump(topology, f, sort_keys=False)


if __name__ == "__main__":
    main()
