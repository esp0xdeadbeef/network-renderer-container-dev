from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import yaml
from clabgen.links import short_bridge
from clabgen.linux_router import render_linux_router
from clabgen.addressing import render_addressing
from clabgen.interfaces import render_interfaces
from clabgen.connected_routes import render_connected_routes
from clabgen.static_routes import render_static_routes
from clabgen.sysctl import render_sysctls


def _collect_sites(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    results = []
    for ent, site_map in data.get("sites", {}).items():
        for site_id, site_obj in site_map.items():
            nodes = site_obj.get("nodes", {})
            links = site_obj.get("links", {})
            results.append({
                "enterprise": ent,
                "siteId": site_id,
                "nodes": nodes,
                "links": links,
                "topology": {
                    "nodes": list(nodes.keys()),
                    "links": list(links.keys()),
                },
            })
    return results


def _interface_index_map(site: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}
    for node_name, node_data in site["nodes"].items():
        iface_names = sorted(node_data.get("interfaces", {}).keys())
        out[node_name] = {ifname: idx + 1 for idx, ifname in enumerate(iface_names)}
    return out


def _render_node_exec(node_raw: Dict[str, Any], eth_map: Dict[str, int]) -> List[str]:
    node = {
        "interfaces": {
            k: {
                "addr4": v.get("addr4"),
                "addr6": v.get("addr6"),
                "routes4": v.get("routes4", []),
                "routes6": v.get("routes6", []),
            }
            for k, v in node_raw.get("interfaces", {}).items()
        }
    }

    cmds = []
    cmds += render_sysctls()
    cmds += render_interfaces(node, eth_map)
    cmds += render_addressing(node, eth_map)
    cmds += render_connected_routes(node, eth_map)
    cmds += render_static_routes(node, eth_map)
    return cmds


def _build_nodes(site: Dict[str, Any], iface_map: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
    ent = site["enterprise"]
    sid = site["siteId"]

    out: Dict[str, Any] = {}

    for node_name, node_data in site["nodes"].items():
        full = f"{ent}-{sid}-{node_name}"
        exec_cmds = _render_node_exec(node_data, iface_map.get(node_name, {}))

        out[full] = {
            "kind": "linux",
            "image": "clab-frr-plus-tooling:latest",
            "exec": exec_cmds,
        }

    return out


def _build_links(site: Dict[str, Any], iface_map: Dict[str, Dict[str, int]]) -> List[Dict[str, Any]]:
    ent = site["enterprise"]
    sid = site["siteId"]

    links_out: List[Dict[str, Any]] = []

    for link_name in site["topology"]["links"]:
        link_def = site["links"][link_name]
        eps = link_def.get("endpoints", {})

        rendered_eps = []
        for unit in sorted(eps.keys()):
            eth_num = iface_map.get(unit, {}).get(link_name, 1)
            rendered_eps.append(f"{ent}-{sid}-{unit}:eth{eth_num}")

        links_out.append({
            "endpoints": rendered_eps,
            "labels": {
                "clab.link.type": "bridge",
                "clab.link.bridge": short_bridge(f"{ent}-{sid}-{link_name}"),
            },
        })

    return links_out


def _collect_bridges(sites: List[Dict[str, Any]]) -> List[str]:
    out = []
    for site in sites:
        ent = site["enterprise"]
        sid = site["siteId"]
        for link_name in site["topology"]["links"]:
            out.append(short_bridge(f"{ent}-{sid}-{link_name}"))
    return sorted(set(out))


def write_outputs(
    solver_json: str | Path,
    topology_out: str | Path,
    bridges_out: str | Path,
) -> None:

    data = json.loads(Path(solver_json).read_text())
    sites = _collect_sites(data)

    merged_nodes: Dict[str, Any] = {}
    merged_links: List[Dict[str, Any]] = []

    for site in sites:
        iface_map = _interface_index_map(site)
        built_nodes = _build_nodes(site, iface_map)
        for k, v in built_nodes.items():
            merged_nodes[k] = v

        merged_links.extend(_build_links(site, iface_map))

    topology = {
        "name": "fabric",
        "topology": {
            "defaults": {
                "kind": "linux",
                "image": "clab-frr-plus-tooling:latest",
                "sysctls": {
                    "net.ipv4.ip_forward": "1",
                    "net.ipv6.conf.all.forwarding": "1",
                    "net.ipv4.conf.all.rp_filter": "0",
                    "net.ipv4.conf.default.rp_filter": "0",
                },
            },
            "nodes": merged_nodes,
            "links": merged_links,
        },
    }

    Path(topology_out).write_text(yaml.dump(topology, sort_keys=False))

    bridges = _collect_bridges(sites)
    Path(bridges_out).write_text(
        "{ lib, ... }:\n{\n  bridges = [\n"
        + "\n".join(f'    "{b}"' for b in bridges)
        + "\n  ];\n}\n"
    )
