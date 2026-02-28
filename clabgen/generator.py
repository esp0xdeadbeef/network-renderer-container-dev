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
            cmds.append(f"ip addr replace {iface.addr4} dev {dev}")
        if iface.addr6:
            cmds.append(f"ip -6 addr replace {iface.addr6} dev {dev}")
        if iface.ll6:
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


def _derive_client_lan(node: NodeModel):
    v4 = v6 = None
    for iface in node.interfaces.values():
        if iface.addr4 and iface.addr4.endswith("/31"):
            v4 = ipaddress.IPv4Interface(iface.addr4)
        if iface.addr6 and iface.addr6.endswith("/127"):
            v6 = ipaddress.IPv6Interface(iface.addr6)

    if not v4 or not v6:
        raise RuntimeError("singleAccess node missing uplink")

    peer4 = list(v4.network.hosts())[0]
    lan4 = ipaddress.IPv4Network(f"{peer4}/24", strict=False)
    peer6 = list(v6.network.hosts())[0]
    base64 = (int(peer6) >> 64) << 64
    lan6 = ipaddress.IPv6Network((base64, 64))

    return (
        f"{lan4.network_address + 1}/24",
        f"{lan4.network_address + 2}/24",
        f"{lan6.network_address + 1}/64",
        f"{lan6.network_address + 2}/64",
    )


def generate_topology(site: SiteModel) -> Dict:
    rendered_nodes: Dict[str, Dict] = {}
    rendered_links: List[Dict] = []
    bridges: Set[str] = set()

    eth_index: Dict[str, Dict[str, int]] = {u: {} for u in site.nodes}

    # assign eth indexes for ALL links (lan + wan)
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

    # deterministic WAN ISP naming per core (do NOT inherit container suffix)
    for lk, link in site.links.items():
        bridge = _short_bridge(f"{site.enterprise}-{site.site}-{lk}")
        bridges.add(bridge)

        units = list(link.endpoints.keys())

        if link.kind == "wan":
            if len(units) != 1:
                continue

            unit = units[0]
            core_rendered_name = unit_name[unit]

            suffix = lk.split("-")[-1]  # isp-a / isp-b
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
                    f"{core_rendered_name}:eth{eth_index[unit][lk]}",
                    f"{isp_name}:eth1",
                ],
                "labels": {
                    "clab.link.type": "bridge",
                    "clab.link.bridge": bridge,
                },
            })

        elif len(units) == 2:
            u1, u2 = units
            rendered_links.append({
                "endpoints": [
                    f"{unit_name[u1]}:eth{eth_index[u1][lk]}",
                    f"{unit_name[u2]}:eth{eth_index[u2][lk]}",
                ],
                "labels": {
                    "clab.link.type": "bridge",
                    "clab.link.bridge": bridge,
                },
            })

    # validation client
    access = site.single_access
    access_node = site.nodes[access]
    access_name = unit_name[access]

    access_v4, client_v4, access_v6, client_v6 = _derive_client_lan(access_node)

    idx = len(eth_index[access]) + 1
    dev = f"eth{idx}"

    rendered_nodes[access_name]["exec"].extend([
        f"ip link set {dev} up",
        f"ip addr replace {access_v4} dev {dev}",
        f"ip -6 addr replace {access_v6} dev {dev}",
    ])

    client_name = f"{access_name}-client"

    rendered_nodes[client_name] = {
        "exec": [
            "sysctl -w net.ipv4.ip_forward=0",
            "sysctl -w net.ipv6.conf.all.forwarding=0",
            "ip link set eth1 up",
            f"ip addr replace {client_v4} dev eth1",
            f"ip -6 addr replace {client_v6} dev eth1",
            f"ip route replace 0.0.0.0/0 via {access_v4.split('/')[0]} dev eth1",
            f"ip -6 route replace ::/0 via {access_v6.split('/')[0]} dev eth1",
        ]
    }

    client_bridge = _short_bridge(f"{site.enterprise}-{site.site}-client")
    bridges.add(client_bridge)

    rendered_links.append({
        "endpoints": [
            f"{client_name}:eth1",
            f"{access_name}:{dev}",
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
