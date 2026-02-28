# ./generate-clab-config.py
#!/usr/bin/env python3

from __future__ import annotations

import sys
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Set

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
DEFAULT_BRIDGES_FILE = "vm-bridges-generated.nix"
IMAGE = "frrouting/frr:latest"
MAX_BR_NAME_LEN = 15


def short_bridge_name(seed: str) -> str:
    h = hashlib.sha1(seed.encode()).hexdigest()[:10]
    name = f"br{h}"
    return name[:MAX_BR_NAME_LEN]


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


def _iface_order(node_obj: Dict[str, Any]) -> List[str]:
    ifaces = node_obj.get("interfaces", {})
    if not isinstance(ifaces, dict):
        return []
    return list(ifaces.keys())


def _pick_primary_container(node_obj: Dict[str, Any]) -> str:
    cs = node_obj.get("containers")
    if isinstance(cs, list) and cs:
        for c in cs:
            if isinstance(c, str) and c:
                return c
    return "default"


def _clab_name_for_unit(ent: str, site: str, unit: str, node_obj: Dict[str, Any]) -> str:
    c = _pick_primary_container(node_obj)
    base = f"{ent}-{site}-{unit}"
    if c == "default":
        return base
    return f"{base}-{c}"


def _render_node(
    node_obj: Dict[str, Any],
    eth_map: Dict[str, int],
) -> Dict[str, Any]:
    exec_cmds: List[str] = [
        "sysctl -w net.ipv4.ip_forward=1",
        "sysctl -w net.ipv6.conf.all.forwarding=1",
    ]

    interfaces = node_obj.get("interfaces", {})
    if not isinstance(interfaces, dict):
        return {"exec": exec_cmds}

    for link_key in interfaces.keys():
        if link_key not in eth_map:
            fail(f"Interface mapping failed for link '{link_key}'", context=node_obj)

        eth_idx = eth_map[link_key]
        dev = f"eth{eth_idx}"

        iface_obj = interfaces.get(link_key)
        if not isinstance(iface_obj, dict):
            fail(f"Invalid interface object for link '{link_key}'", context=node_obj)

        exec_cmds.append(f"ip link set {dev} up")

        addr4 = iface_obj.get("addr4")
        addr6 = iface_obj.get("addr6")
        ll6 = iface_obj.get("ll6")

        if isinstance(addr4, str) and addr4:
            exec_cmds.append(f"ip addr replace {addr4} dev {dev}")
        if isinstance(addr6, str) and addr6:
            exec_cmds.append(f"ip -6 addr replace {addr6} dev {dev}")
        if isinstance(ll6, str) and ll6:
            exec_cmds.append(f"ip -6 addr replace {ll6} dev {dev}")

        exec_cmds.extend(_emit_iface_routes(iface_obj, 4, dev))
        exec_cmds.extend(_emit_iface_routes(iface_obj, 6, dev))

    return {"exec": exec_cmds}


def _render_synthetic_isp_node() -> Dict[str, Any]:
    return {
        "exec": [
            "sysctl -w net.ipv4.ip_forward=1",
            "sysctl -w net.ipv6.conf.all.forwarding=1",
            "ip link set eth1 up",
        ]
    }


def write_bridges_file(bridges: Set[str], path: Path) -> None:
    bridge_list = sorted(bridges)

    lines: List[str] = []
    lines.append("{ lib, ... }:")
    lines.append("{")
    lines.append("  bridges = [")
    for b in bridge_list:
        lines.append(f'    "{b}"')
    lines.append("  ];")
    lines.append("}")

    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    solver_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_SOLVER_JSON)
    topo_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(DEFAULT_TOPO_FILE)
    bridges_path = (
        Path(sys.argv[3]) if len(sys.argv) > 3 else Path(DEFAULT_BRIDGES_FILE)
    )

    data = load_solver(solver_path)
    sites = extract_enterprise_sites(data)

    rendered_nodes: Dict[str, Any] = {}
    rendered_links: List[Dict[str, Any]] = []
    bridge_names: Set[str] = set()

    for ent_name, site_name, site in sites:
        site_ctx = {"enterprise": ent_name, "site": site_name, "siteObj": site}

        validate_site_invariants(site, context=site_ctx)
        validate_routing_assumptions(site, context=site_ctx)

        nodes_any = site.get("nodes")
        links_any = site.get("links")

        if not isinstance(nodes_any, dict):
            fail("Invalid solver structure: site.nodes missing", context=site_ctx)
        if not isinstance(links_any, dict):
            fail("Invalid solver structure: site.links missing", context=site_ctx)

        nodes: Dict[str, Dict[str, Any]] = {}
        for n, o in nodes_any.items():
            if not isinstance(n, str) or not isinstance(o, dict):
                fail(f"Invalid node definition at '{n}'", context=site_ctx)
            nodes[n] = o

        links: Dict[str, Dict[str, Any]] = {}
        for lk, lo in links_any.items():
            if not isinstance(lk, str) or not isinstance(lo, dict):
                fail(f"Invalid link definition at '{lk}'", context=site_ctx)
            links[lk] = lo

        unit_to_clab: Dict[str, str] = {
            unit: _clab_name_for_unit(ent_name, site_name, unit, node_obj)
            for unit, node_obj in nodes.items()
        }

        eth_index: Dict[str, Dict[str, int]] = {u: {} for u in nodes.keys()}
        isp_nodes_for_site: Set[str] = set()

        # Assign interface indices deterministically
        for link_key, link_obj in sorted(links.items()):
            eps = link_obj.get("endpoints")
            if not isinstance(eps, dict):
                fail(f"Link '{link_key}' missing endpoints", context=site_ctx)

            for unit in eps.keys():
                if unit not in nodes:
                    fail(f"Link '{link_key}' references unknown unit '{unit}'", context=site_ctx)

                if link_key not in nodes[unit].get("interfaces", {}):
                    fail(
                        f"Link '{link_key}' missing interface mapping on unit '{unit}'",
                        context=site_ctx,
                    )

                if link_key not in eth_index[unit]:
                    eth_index[unit][link_key] = len(eth_index[unit]) + 1

        # Render regular nodes
        for unit in sorted(nodes.keys()):
            clab_name = unit_to_clab[unit]
            rendered_nodes[clab_name] = _render_node(
                nodes[unit],
                eth_index.get(unit, {}),
            )

        # Render links
        for link_key, link_obj in sorted(links.items()):
            eps = link_obj.get("endpoints")
            kind = link_obj.get("kind")

            if not isinstance(eps, dict):
                fail(f"Link '{link_key}' missing endpoints", context=site_ctx)

            seed = f"{ent_name}-{site_name}-{link_key}"
            bridge_name = short_bridge_name(seed)
            bridge_names.add(bridge_name)

            if kind == "wan":
                if len(eps) != 1:
                    fail(
                        f"WAN link '{link_key}' must have exactly 1 solver endpoint",
                        context=site_ctx,
                    )

                unit = next(iter(eps.keys()))
                if unit not in unit_to_clab:
                    fail(f"WAN link '{link_key}' unknown unit '{unit}'", context=site_ctx)

                if link_key not in eth_index[unit]:
                    fail(
                        f"WAN link '{link_key}' missing interface index for '{unit}'",
                        context=site_ctx,
                    )

                eth = eth_index[unit][link_key]
                core_ref = f"{unit_to_clab[unit]}:eth{eth}"

                # Determine ISP name deterministically per site
                isp_index = len(isp_nodes_for_site)
                isp_suffix = chr(ord("a") + isp_index)
                isp_name = f"{ent_name}-{site_name}-isp-{isp_suffix}"

                if isp_name not in rendered_nodes:
                    rendered_nodes[isp_name] = _render_synthetic_isp_node()
                    isp_nodes_for_site.add(isp_name)

                isp_ref = f"{isp_name}:eth1"

                rendered_links.append(
                    {
                        "endpoints": [core_ref, isp_ref],
                        "labels": {
                            "clab.link.type": "bridge",
                            "clab.link.bridge": bridge_name,
                        },
                    }
                )
            else:
                if len(eps) != 2:
                    fail(
                        f"Link '{link_key}' must have exactly 2 endpoints",
                        context=site_ctx,
                    )

                endpoint_refs: List[str] = []

                for unit in sorted(eps.keys()):
                    if unit not in unit_to_clab:
                        fail(f"Link '{link_key}' unknown unit '{unit}'", context=site_ctx)

                    if link_key not in eth_index[unit]:
                        fail(
                            f"Link '{link_key}' missing interface index for '{unit}'",
                            context=site_ctx,
                        )

                    eth = eth_index[unit][link_key]
                    endpoint_refs.append(f"{unit_to_clab[unit]}:eth{eth}")

                rendered_links.append(
                    {
                        "endpoints": endpoint_refs,
                        "labels": {
                            "clab.link.type": "bridge",
                            "clab.link.bridge": bridge_name,
                        },
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
                },
            },
            "nodes": rendered_nodes,
            "links": rendered_links,
        },
    }

    with topo_path.open("w") as f:
        yaml.dump(topology, f, sort_keys=False)

    write_bridges_file(bridge_names, bridges_path)


if __name__ == "__main__":
    main()
