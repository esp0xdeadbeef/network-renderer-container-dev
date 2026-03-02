from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Set

import yaml

from .parser import parse_solver
from .generator import generate_topology


def _strip_network_mode(obj: Any) -> None:
    if isinstance(obj, dict):
        obj.pop("network-mode", None)
        for v in obj.values():
            _strip_network_mode(v)
    elif isinstance(obj, list):
        for v in obj:
            _strip_network_mode(v)


def build_fabric_topology_from_solver(solver_json: str | Path) -> Dict[str, Any]:
    sites = parse_solver(solver_json)

    merged_nodes: Dict[str, Any] = {}
    merged_links: List[Dict[str, Any]] = []
    bridges: Set[str] = set()

    for site in sites.values():
        topo = generate_topology(site)
        merged_nodes.update(topo["topology"]["nodes"])
        merged_links.extend(topo["topology"]["links"])
        bridges.update(topo.get("bridges", []))

    final_topology: Dict[str, Any] = {
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

    _strip_network_mode(final_topology)
    return final_topology


def write_topology_yaml(topology: Dict[str, Any], output_path: str | Path) -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.dump(topology, sort_keys=False))


def build_vm_bridges_nix(bridges: List[str]) -> str:
    lines: List[str] = [
        "{ lib, ... }:",
        "{",
        "  bridges = [",
    ]
    for b in sorted(set(bridges)):
        lines.append(f'    "{b}"')
    lines.extend(
        [
            "  ];",
            "}",
            "",
        ]
    )
    return "\n".join(lines)


def write_vm_bridges_nix(bridges: List[str], output_path: str | Path) -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_vm_bridges_nix(bridges))


def write_outputs(
    solver_json: str | Path,
    topology_out: str | Path,
    bridges_out: str | Path,
) -> None:
    sites = parse_solver(solver_json)

    merged_nodes: Dict[str, Any] = {}
    merged_links: List[Dict[str, Any]] = []
    bridges: Set[str] = set()

    for site in sites.values():
        topo = generate_topology(site)
        merged_nodes.update(topo["topology"]["nodes"])
        merged_links.extend(topo["topology"]["links"])
        bridges.update(topo.get("bridges", []))

    final_topology: Dict[str, Any] = {
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

    _strip_network_mode(final_topology)

    write_topology_yaml(final_topology, topology_out)
    write_vm_bridges_nix(sorted(bridges), bridges_out)
