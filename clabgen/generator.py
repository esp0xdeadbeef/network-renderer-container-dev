from __future__ import annotations

from typing import Dict, Set, List
import copy
import json
from pathlib import Path

from .models import SiteModel
from .nodes import render_node
from .links import build_eth_index, short_bridge
from .isp import ensure_isp_node


def scoped_name(site: SiteModel, unit: str) -> str:
    return f"{site.enterprise}-{site.site}-{unit}"


def _load_raw_site(site: SiteModel) -> Dict:
    solver_path = Path("output-network-solver.json")
    if not solver_path.exists():
        return {}

    with solver_path.open() as f:
        data = json.load(f)

    return (
        data.get("sites", {})
        .get(site.enterprise, {})
        .get(site.site, {})
    )


def _derive_policy_owner(raw_site: Dict) -> str:
    owner = raw_site.get("_enforcement", {}).get("owner")
    if not owner:
        return ""
    return owner


def _stringify_exec(node_def: Dict) -> Dict:
    if "exec" not in node_def:
        return node_def
    node_def["exec"] = [str(e) for e in node_def["exec"]]
    return node_def


def generate_topology(site: SiteModel) -> Dict:
    site = copy.deepcopy(site)

    if not site.nodes or not site.links:
        return {
            "name": f"{site.enterprise}-{site.site}",
            "topology": {
                "defaults": {
                    "kind": "linux",
                    "image": "clab-frr-plus-tooling:latest",
                    "network-mode": "none",
                },
                "nodes": {},
                "links": [],
            },
            "bridges": [],
        }

    raw_site = _load_raw_site(site)

    rendered_nodes: Dict[str, Dict] = {}
    rendered_links: List[Dict] = []
    bridges: Set[str] = set()

    policy_owner = _derive_policy_owner(raw_site)

    rename_map: Dict[str, str] = {}

    attachments = (
        raw_site
        .get("_debug", {})
        .get("compilerIR", {})
        .get("attachment", [])
    )
    for att in attachments:
        if att.get("segment") == "tenants:mgmt":
            unit = att.get("unit")
            if unit in site.nodes and policy_owner:
                rename_map[unit] = f"{unit}-{policy_owner}"

    for old, new in rename_map.items():
        site.nodes[new] = site.nodes.pop(old)

    for link in site.links.values():
        updated = {}
        for unit, data in link.endpoints.items():
            updated[rename_map.get(unit, unit)] = data
        link.endpoints = updated

    eth_index = build_eth_index(site)

    for unit, node in site.nodes.items():
        full_name = scoped_name(site, unit)

        if node.role == "isp":
            ensure_isp_node(rendered_nodes, full_name, None)
            continue

        rendered = render_node(node, eth_index.get(unit, {}))
        rendered_nodes[full_name] = _stringify_exec(rendered)

    # ALWAYS render links as bridges (containerlab VM requires explicit bridges)
    for link_name, link in site.links.items():
        eps = list(link.endpoints.keys())
        if len(eps) != 2:
            continue

        bridge = short_bridge(f"{site.enterprise}-{site.site}-{link_name}")
        bridges.add(bridge)

        endpoints = []
        for unit in eps:
            full_name = scoped_name(site, unit)
            eth_num = eth_index[unit][link_name]
            endpoints.append(f"{full_name}:eth{eth_num}")

        rendered_links.append(
            {
                "endpoints": endpoints,
                "labels": {
                    "clab.link.type": "bridge",
                    "clab.link.bridge": bridge,
                },
            }
        )

    return {
        "name": f"{site.enterprise}-{site.site}",
        "topology": {
            "defaults": {
                "kind": "linux",
                "image": "clab-frr-plus-tooling:latest",
                "network-mode": "none",
            },
            "nodes": rendered_nodes,
            "links": rendered_links,
        },
        "bridges": sorted(list(bridges)),
    }
