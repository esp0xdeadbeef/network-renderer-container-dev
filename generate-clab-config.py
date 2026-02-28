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
            if isinstance(via, str) and via:
                cmds.append(f"ip route replace {dst} via {via} dev {dev}")
            else:
                cmds.append(f"ip route replace {dst} dev {dev}")
        else:
            via = r.get("via6")
            if isinstance(via, str) and via:
                cmds.append(f"ip -6 route replace {dst} via {via} dev {dev}")
            else:
                cmds.append(f"ip -6 route replace {dst} dev {dev}")

    return cmds


def _is_strict_p2p(link_obj: Any) -> bool:
    return (
        isinstance(link_obj, dict)
        and link_obj.get("kind") == "p2p"
        and isinstance(link_obj.get("endpoints"), dict)
        and len(link_obj["endpoints"]) == 2
    )


def _is_wan(link_obj: Any) -> bool:
    return (
        isinstance(link_obj, dict)
        and link_obj.get("kind") == "wan"
        and isinstance(link_obj.get("endpoints"), dict)
        and len(link_obj["endpoints"]) == 1
        and isinstance(link_obj.get("upstream"), str)
        and bool(link_obj.get("upstream"))
    )


def _eth_index_for_node(
    node: str,
    link_key: str,
    relevant_links: Dict[str, Dict[str, Any]],
) -> int:
    idx = 1
    for lk in sorted(relevant_links.keys()):
        lo = relevant_links[lk]
        eps = lo.get("endpoints")
        if not isinstance(eps, dict) or node not in eps:
            continue
        if lk == link_key:
            return idx
        idx += 1
    return 1


def _render_node(
    node_name: str,
    node_obj: Dict[str, Any],
    relevant_links: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    exec_cmds: List[str] = [
        "sysctl -w net.ipv4.ip_forward=1",
        "sysctl -w net.ipv6.conf.all.forwarding=1",
    ]

    interfaces = node_obj.get("interfaces", {})
    if not isinstance(interfaces, dict):
        return {"exec": exec_cmds}

    eth_idx = 1
    for link_key in sorted(relevant_links.keys()):
        link_obj = relevant_links[link_key]
        eps = link_obj.get("endpoints")
        if not isinstance(eps, dict) or node_name not in eps:
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
    isp_eth_next: Dict[str, int] = {}

    for ent_name, site_name, site in sites:
        site_ctx = {"enterprise": ent_name, "site": site_name, "siteObj": site}

        validate_site_invariants(site, context=site_ctx)
        validate_routing_assumptions(site, context=site_ctx)

        nodes = site.get("nodes", {})
        links = site.get("links", {})

        if not isinstance(nodes, dict) or not isinstance(links, dict):
            fail("Invalid solver structure: nodes/links missing", context=site_ctx)

        # remove isolated nodes (access, core)
        filtered_nodes = {
            name: obj
            for name, obj in nodes.items()
            if not bool(obj.get("isolated"))
        }

        debug = site.get("_debug", {})
        compiler_ir = debug.get("compilerIR", {})
        upstreams = compiler_ir.get("upstreams", {})
        cores = upstreams.get("cores", {})

        for _, upstream_list in cores.items():
            if not isinstance(upstream_list, list):
                continue
            for up in upstream_list:
                if not isinstance(up, dict):
                    continue
                upstream_name = up.get("name")
                if not isinstance(upstream_name, str) or not upstream_name:
                    continue

                isp_full = f"{ent_name}-{site_name}-isp-{upstream_name}"
                if isp_full not in rendered_nodes:
                    rendered_nodes[isp_full] = {
                        "exec": [
                            "sysctl -w net.ipv4.ip_forward=1",
                            "sysctl -w net.ipv6.conf.all.forwarding=1",
                        ]
                    }
                    isp_eth_next[isp_full] = 1

        relevant_links: Dict[str, Dict[str, Any]] = {}
        for lk, lo in links.items():
            if not (_is_strict_p2p(lo) or _is_wan(lo)):
                continue

            eps = lo.get("endpoints", {})
            if any(node in filtered_nodes for node in eps.keys()):
                relevant_links[lk] = lo

        for node_name in sorted(filtered_nodes.keys()):
            node_obj = filtered_nodes[node_name]
            rendered_nodes[f"{ent_name}-{site_name}-{node_name}"] = _render_node(
                node_name, node_obj, relevant_links
            )

        for link_key in sorted(relevant_links.keys()):
            link_obj = relevant_links[link_key]

            if _is_strict_p2p(link_obj):
                eps = link_obj["endpoints"]
                a, b = sorted(eps.keys())
                if a not in filtered_nodes or b not in filtered_nodes:
                    continue

                rendered_links.append(
                    {
                        "endpoints": [
                            f"{ent_name}-{site_name}-{a}:eth{_eth_index_for_node(a, link_key, relevant_links)}",
                            f"{ent_name}-{site_name}-{b}:eth{_eth_index_for_node(b, link_key, relevant_links)}",
                        ]
                    }
                )
                continue

            if _is_wan(link_obj):
                upstream = link_obj["upstream"]
                eps = link_obj["endpoints"]
                core_node = next(iter(eps.keys()))

                if core_node not in filtered_nodes:
                    continue

                isp_full = f"{ent_name}-{site_name}-isp-{upstream}"
                core_full = f"{ent_name}-{site_name}-{core_node}"

                isp_eth = isp_eth_next.get(isp_full, 1)
                isp_eth_next[isp_full] = isp_eth + 1

                core_eth = _eth_index_for_node(core_node, link_key, relevant_links)

                rendered_links.append(
                    {
                        "endpoints": [
                            f"{core_full}:eth{core_eth}",
                            f"{isp_full}:eth{isp_eth}",
                        ]
                    }
                )
                continue

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
