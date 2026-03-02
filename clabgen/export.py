# ./clabgen/export.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import yaml


def _first_site(data: Dict[str, Any]) -> Dict[str, Any]:
    sites = data["sites"]
    enterprise = next(iter(sites.values()))
    site = next(iter(enterprise.values()))
    return site


def _build_nodes(site: Dict[str, Any]) -> Dict[str, Any]:
    enterprise = site["enterprise"]
    site_id = site["siteId"]

    nodes: Dict[str, Any] = {}

    for node_name in site["topology"]["nodes"]:
        full_name = f"{enterprise}-{site_id}-{node_name}"
        nodes[full_name] = {
            "kind": "linux",
            "image": "clab-frr-plus-tooling:latest",
        }

    return nodes


def _interface_index_map(site: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    result: Dict[str, Dict[str, str]] = {}

    for node_name, node_data in site["nodes"].items():
        iface_names = sorted(node_data["interfaces"].keys())
        result[node_name] = {}
        for idx, ifname in enumerate(iface_names, start=1):
            result[node_name][ifname] = f"eth{idx}"

    return result


def _build_links(site: Dict[str, Any]) -> List[Dict[str, Any]]:
    enterprise = site["enterprise"]
    site_id = site["siteId"]

    iface_map = _interface_index_map(site)

    links: List[Dict[str, Any]] = []

    for link_name in site["topology"]["links"]:
        link_def = site["links"][link_name]
        endpoints = link_def["endpoints"]

        eps: List[str] = []
        for unit in sorted(endpoints.keys()):
            full_node = f"{enterprise}-{site_id}-{unit}"
            eth = iface_map[unit][link_name]
            eps.append(f"{full_node}:{eth}")

        links.append({"endpoints": eps})

    return links


def write_outputs(
    solver_json: str | Path,
    topology_out: str | Path,
    bridges_out: str | Path,
) -> None:
    data = json.loads(Path(solver_json).read_text())
    site = _first_site(data)

    topology_dict: Dict[str, Any] = {
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
            "nodes": _build_nodes(site),
            "links": _build_links(site),
        },
    }

    yaml_text = yaml.dump(topology_dict, sort_keys=False)
    Path(topology_out).write_text(yaml_text)

    Path(bridges_out).write_text(
        "{ lib, ... }:\n{\n  bridges = [ ];\n}\n"
    )
