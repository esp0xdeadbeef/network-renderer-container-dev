from __future__ import annotations

from typing import Dict, Any, List
from pathlib import Path
import copy
import hashlib

from clabgen.models import SiteModel
from clabgen.s88.enterprise.site_loader import load_sites
from clabgen.s88.enterprise.inject_wan_peers import inject_emulated_wan_peers
from clabgen.s88.engine import render_node_s88


def _short_bridge(name: str) -> str:
    h = hashlib.blake2s(name.encode(), digest_size=6).hexdigest()
    return f"br-{h}"


def _host_ifname(bridge: str) -> str:
    h = hashlib.blake2s(bridge.encode(), digest_size=2).hexdigest()
    return f"veth-{bridge[:6]}-{h}"


def _build_eth_maps(site: SiteModel) -> Dict[str, Dict[str, int]]:
    eth_maps: Dict[str, Dict[str, int]] = {n: {} for n in site.nodes}
    counters: Dict[str, int] = {n: 1 for n in site.nodes}

    for link_name in sorted(site.links.keys()):
        link = site.links[link_name]

        for node_name, ep in sorted(link.endpoints.items()):
            if node_name not in site.nodes:
                continue

            iface = ep.get("interface")
            if iface is None:
                continue

            if iface not in eth_maps[node_name]:
                eth_maps[node_name][iface] = counters[node_name]
                counters[node_name] += 1

    for node_name in sorted(site.nodes.keys()):
        node = site.nodes[node_name]
        for ifname in sorted(node.interfaces.keys()):
            iface = node.interfaces[ifname]
            if iface.kind == "tenant" and ifname not in eth_maps[node_name]:
                eth_maps[node_name][ifname] = counters[node_name]
                counters[node_name] += 1

    return eth_maps


def generate_topology(site: SiteModel) -> Dict[str, Any]:
    site = copy.deepcopy(site)
    inject_emulated_wan_peers(site)

    eth_maps = _build_eth_maps(site)

    nodes: Dict[str, Any] = {}
    links: List[Dict[str, Any]] = []
    bridges: List[str] = []

    for node_name in sorted(site.nodes.keys()):
        node = site.nodes[node_name]
        eth_map = eth_maps.get(node_name, {})

        node_dict = {
            "name": node_name,
            "role": node.role,
            "interfaces": {
                ifname: {
                    "addr4": iface.addr4,
                    "addr6": iface.addr6,
                    "ll6": iface.ll6,
                    "kind": iface.kind,
                    "upstream": iface.upstream,
                    "routes": copy.deepcopy(iface.routes),
                }
                for ifname, iface in sorted(node.interfaces.items())
                if ifname in eth_map
            },
            "route_intents": list(node.route_intents),
        }

        exec_cmds = render_node_s88(node_name, node_dict, eth_map)

        nodes[node_name] = {
            "kind": "linux",
            "image": "clab-frr-plus-tooling:latest",
            "exec": exec_cmds,
        }

    for link_name in sorted(site.links.keys()):
        link = site.links[link_name]
        endpoints: List[str] = []

        for node_name, ep in sorted(link.endpoints.items()):
            if node_name not in eth_maps:
                continue

            iface = ep.get("interface")
            if iface is None:
                continue

            if iface not in eth_maps[node_name]:
                continue

            eth_index = eth_maps[node_name][iface]
            endpoints.append(f"{node_name}:eth{eth_index}")

        if len(endpoints) == 2:
            bridge = _short_bridge(f"{site.enterprise}-{site.site}-{link_name}")
            bridges.append(bridge)
            links.append(
                {
                    "endpoints": endpoints,
                    "labels": {
                        "clab.link.type": "bridge",
                        "clab.link.bridge": bridge,
                    },
                }
            )

    tenant_groups: Dict[str, List[str]] = {}

    for node_name in sorted(site.nodes.keys()):
        node = site.nodes[node_name]
        for ifname, iface in sorted(node.interfaces.items()):
            if iface.kind != "tenant":
                continue

            eth = eth_maps[node_name].get(ifname)
            if eth is None:
                continue

            tenant_groups.setdefault(ifname, []).append(f"{node_name}:eth{eth}")

    for tenant in sorted(tenant_groups.keys()):
        bridge = _short_bridge(f"{site.enterprise}-{site.site}-tenant-{tenant}")
        bridges.append(bridge)

        endpoints = list(tenant_groups[tenant])
        if len(endpoints) == 1:
            endpoints.append(f"host:{_host_ifname(bridge)}")

        links.append(
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
            },
            "nodes": nodes,
            "links": links,
        },
        "bridges": sorted(set(bridges)),
        "bridge_control_modules": {},
        "solver_meta": dict(site.solver_meta),
    }


class Enterprise:
    def __init__(self, sites: Dict[str, SiteModel]) -> None:
        self.sites = sites

    @classmethod
    def from_solver_json(cls, solver_json: str | Path) -> "Enterprise":
        sites = load_sites(solver_json)
        return cls(sites)

    def render(self) -> Dict[str, Any]:
        merged_nodes: Dict[str, Any] = {}
        merged_links: List[Dict[str, Any]] = []
        merged_bridges: List[str] = []

        defaults: Dict[str, Any] | None = None
        solver_meta: Dict[str, Any] | None = None

        for site_key in sorted(self.sites.keys()):
            topo = generate_topology(self.sites[site_key])

            if defaults is None:
                defaults = topo["topology"]["defaults"]

            if solver_meta is None:
                solver_meta = dict(topo.get("solver_meta", {}) or {})

            for node_name, node_def in topo["topology"]["nodes"].items():
                if node_name in merged_nodes:
                    raise ValueError(f"duplicate rendered node '{node_name}'")
                merged_nodes[node_name] = node_def

            merged_links.extend(topo["topology"]["links"])
            merged_bridges.extend(topo.get("bridges", []))

        return {
            "name": "fabric",
            "topology": {
                "defaults": defaults or {},
                "nodes": merged_nodes,
                "links": merged_links,
            },
            "bridges": sorted(set(merged_bridges)),
            "bridge_control_modules": {},
            "solver_meta": solver_meta or {},
        }
