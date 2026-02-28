# FILE: ./clabgen/generator.py
from __future__ import annotations

import hashlib
import ipaddress
from typing import Dict, List, Set

from .models import SiteModel, NodeModel


def _short_bridge(seed: str) -> str:
    return "br" + hashlib.sha1(seed.encode()).hexdigest()[:10]


def _container_suffix(node: NodeModel) -> str:
    if node.containers and node.containers[0] != "default":
        return f"-{node.containers[0]}"
    return ""


def _scoped_name(site: SiteModel, node: NodeModel) -> str:
    return f"{site.enterprise}-{site.site}-{node.name}{_container_suffix(node)}"


def _validate_prefix_preserved(addr: str) -> None:
    if "/" not in addr:
        raise RuntimeError(f"Invalid address without prefix: {addr}")


def _peer_p2p(addr: str) -> str:
    iface = ipaddress.ip_interface(addr)
    hosts = list(iface.network.hosts())
    if len(hosts) != 2:
        raise RuntimeError("P2P network must have exactly two hosts")
    peer = hosts[0] if hosts[1] == iface.ip else hosts[1]
    return f"{peer}/{iface.network.prefixlen}"


def _render_node(node: NodeModel, eth_map: Dict[str, int]) -> Dict:
    cmds: List[str] = [
        "sysctl -w net.ipv4.ip_forward=1",
        "sysctl -w net.ipv6.conf.all.forwarding=1",
    ]

    for link_key, iface in node.interfaces.items():
        if link_key not in eth_map:
            continue

        dev = f"eth{eth_map[link_key]}"
        cmds.append(f"ip link set {dev} up")

        if iface.addr4:
            _validate_prefix_preserved(iface.addr4)
            cmds.append(f"ip addr replace {iface.addr4} dev {dev}")
        if iface.addr6:
            _validate_prefix_preserved(iface.addr6)
            cmds.append(f"ip -6 addr replace {iface.addr6} dev {dev}")
        if iface.ll6:
            _validate_prefix_preserved(iface.ll6)
            cmds.append(f"ip -6 addr replace {iface.ll6} dev {dev}")

        for r in iface.routes4:
            if "via4" in r:
                cmds.append(f"ip route replace {r['dst']} via {r['via4']} dev {dev}")
            elif "dst" in r:
                cmds.append(f"ip route replace {r['dst']} dev {dev}")

        for r in iface.routes6:
            if "via6" in r:
                cmds.append(f"ip -6 route replace {r['dst']} via {r['via6']} dev {dev}")
            elif "dst" in r:
                cmds.append(f"ip -6 route replace {r['dst']} dev {dev}")

    return {"exec": cmds}


def generate_topology(site: SiteModel) -> Dict:
    rendered_nodes: Dict[str, Dict] = {}
    rendered_links: List[Dict] = []
    bridges: Set[str] = set()

    eth_index: Dict[str, Dict[str, int]] = {u: {} for u in site.nodes}

    for lk, link in site.links.items():
        for unit in link.endpoints.keys():
            if unit in eth_index:
                eth_index[unit][lk] = len(eth_index[unit]) + 1

    unit_name = {
        u: _scoped_name(site, node)
        for u, node in site.nodes.items()
    }

    for u, node in site.nodes.items():
        rendered_nodes[unit_name[u]] = _render_node(node, eth_index[u])

    for lk, link in site.links.items():
        bridge = _short_bridge(f"{site.enterprise}-{site.site}-{lk}")
        bridges.add(bridge)

        units = list(link.endpoints.keys())

        # WAN: solver defines only core side, we synthesize ISP side
        if link.kind == "wan":
            if len(units) != 1:
                raise RuntimeError(f"WAN link must have exactly one endpoint: {lk}")

            unit = units[0]
            core_name = unit_name[unit]
            suffix = lk.split("-")[-1]
            isp_name = f"{site.enterprise}-{site.site}-{unit}-isp-{suffix}"

            if isp_name not in rendered_nodes:
                rendered_nodes[isp_name] = {
                    "exec": [
                        "sysctl -w net.ipv4.ip_forward=1",
                        "sysctl -w net.ipv6.conf.all.forwarding=1",
                        "ip link set eth1 up",
                    ]
                }

            rendered_links.append({
                "endpoints": [
                    f"{core_name}:eth{eth_index[unit][lk]}",
                    f"{isp_name}:eth1",
                ],
                "labels": {
                    "clab.link.type": "bridge",
                    "clab.link.bridge": bridge,
                },
            })
            continue

        if len(units) != 2:
            raise RuntimeError(f"Link must have exactly two endpoints: {lk}")

        u1, u2 = units
        labels = {
            "clab.link.type": "bridge",
            "clab.link.bridge": bridge,
        }
        if link.kind == "p2p":
            labels["clab.link.mode"] = "p2p"

        rendered_links.append({
            "endpoints": [
                f"{unit_name[u1]}:eth{eth_index[u1][lk]}",
                f"{unit_name[u2]}:eth{eth_index[u2][lk]}",
            ],
            "labels": labels,
        })

    # ACCESS CLIENT
    access = site.single_access
    access_node = site.nodes[access]
    access_rendered = unit_name[access]

    uplink_iface = None
    for iface in access_node.interfaces.values():
        if iface.addr4 and iface.addr4.endswith("/31"):
            uplink_iface = iface
            break
        if iface.addr6 and iface.addr6.endswith("/127"):
            uplink_iface = iface
            break

    if uplink_iface is None:
        raise RuntimeError("Access node missing /31 or /127 uplink")

    client_name = f"{access_rendered}-client"
    eth_client = 1
    eth_access = len(eth_index[access]) + 1

    cmds = [
        "sysctl -w net.ipv4.ip_forward=0",
        "sysctl -w net.ipv6.conf.all.forwarding=0",
        f"ip link set eth{eth_client} up",
    ]

    if uplink_iface.addr4:
        peer4 = _peer_p2p(uplink_iface.addr4)
        _validate_prefix_preserved(peer4)
        cmds.append(f"ip addr replace {peer4} dev eth{eth_client}")
        gw4 = uplink_iface.addr4.split("/")[0]
        cmds.append(f"ip route replace 0.0.0.0/0 via {gw4} dev eth{eth_client}")

    if uplink_iface.addr6:
        peer6 = _peer_p2p(uplink_iface.addr6)
        _validate_prefix_preserved(peer6)
        cmds.append(f"ip -6 addr replace {peer6} dev eth{eth_client}")
        gw6 = uplink_iface.addr6.split("/")[0]
        cmds.append(f"ip -6 route replace ::/0 via {gw6} dev eth{eth_client}")

    rendered_nodes[client_name] = {"exec": cmds}

    client_bridge = _short_bridge(f"{site.enterprise}-{site.site}-client")
    bridges.add(client_bridge)

    rendered_nodes[access_rendered]["exec"].append(
        f"ip link set eth{eth_access} up"
    )

    rendered_links.append({
        "endpoints": [
            f"{client_name}:eth{eth_client}",
            f"{access_rendered}:eth{eth_access}",
        ],
        "labels": {
            "clab.link.type": "bridge",
            "clab.link.bridge": client_bridge,
        },
    })

    return {
        "name": f"{site.enterprise}-{site.site}",
        "topology": {
            "defaults": {
                "kind": "linux",
                "image": "frrouting/frr:latest",
                "network-mode": "none",
            },
            "nodes": rendered_nodes,
            "links": rendered_links,
        },
        "bridges": bridges,
    }
