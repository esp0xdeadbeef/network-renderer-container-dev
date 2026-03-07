from __future__ import annotations

from typing import Dict, Any, List
import copy
import hashlib
import ipaddress

from clabgen.models import SiteModel, NodeModel, InterfaceModel


MAX_HOSTNAME = 63


def _peer_cidr(cidr: str) -> str:
    iface = ipaddress.ip_interface(cidr)
    current = iface.ip
    network = iface.network

    if isinstance(network, ipaddress.IPv4Network):
        candidates = list(network.hosts())
        if not candidates and network.prefixlen == 31:
            candidates = list(network)
    else:
        candidates = list(network.hosts())
        if not candidates and network.prefixlen == 127:
            candidates = list(network)

    for cand in candidates:
        if cand != current:
            return f"{cand}/{network.prefixlen}"

    raise ValueError(f"cannot derive peer address from {cidr}")


def _normalize_prefix(prefix: str) -> str:
    return str(ipaddress.ip_network(prefix, strict=False))


def _route_lists(iface: InterfaceModel) -> Dict[str, List[Dict[str, Any]]]:
    return {
        "ipv4": list((iface.routes or {}).get("ipv4", [])),
        "ipv6": list((iface.routes or {}).get("ipv6", [])),
    }


def _short_name(link: str, node: str, iface: str) -> str:
    base = f"wan-peer-{node}-{iface}"
    if len(base) <= MAX_HOSTNAME:
        return base

    digest = hashlib.blake2s(
        f"{link}:{node}:{iface}".encode(),
        digest_size=4,
    ).hexdigest()
    keep = MAX_HOSTNAME - len(digest) - 1
    return f"{base[:keep]}-{digest}"


def inject_emulated_wan_peers(site: SiteModel) -> None:
    for link_name, link in list(site.links.items()):
        if link.kind != "wan":
            continue

        endpoints = list(link.endpoints.items())
        if len(endpoints) != 1:
            continue

        node_name, ep = endpoints[0]
        iface_name = ep["interface"]
        injected_node_name = _short_name(link_name, node_name, iface_name)

        if injected_node_name in site.nodes:
            continue

        site.nodes[injected_node_name] = NodeModel(
            name=injected_node_name,
            role="wan-peer",
            routing_domain="",
            interfaces={},
        )

        peer_ep: Dict[str, Any] = {
            "node": injected_node_name,
            "interface": iface_name,
        }

        if ep.get("addr4"):
            peer_ep["addr4"] = _peer_cidr(ep["addr4"])

        if ep.get("addr6"):
            peer_ep["addr6"] = _peer_cidr(ep["addr6"])

        link.endpoints[injected_node_name] = peer_ep

        peer_routes4: List[Dict[str, Any]] = []
        peer_routes6: List[Dict[str, Any]] = []

        for other_node_name, other_node in site.nodes.items():
            if other_node_name == injected_node_name:
                continue

            for other_iface in other_node.interfaces.values():
                if other_iface.kind == "wan":
                    continue

                routes = _route_lists(other_iface)

                for route in routes["ipv4"]:
                    if route.get("proto") != "connected":
                        continue

                    dst = route.get("dst") or route.get("to")
                    if not dst or not ep.get("addr4"):
                        continue

                    peer_routes4.append(
                        {
                            "dst": _normalize_prefix(dst),
                            "via4": ep["addr4"].split("/")[0],
                        }
                    )

                for route in routes["ipv6"]:
                    if route.get("proto") != "connected":
                        continue

                    dst = route.get("dst") or route.get("to")
                    if not dst or not ep.get("addr6"):
                        continue

                    peer_routes6.append(
                        {
                            "dst": _normalize_prefix(dst),
                            "via6": ep["addr6"].split("/")[0],
                        }
                    )

        print(f"WARNING {injected_node_name} injected to the config.")
        site.nodes[injected_node_name].interfaces[iface_name] = InterfaceModel(
            name=iface_name,
            addr4=peer_ep.get("addr4"),
            addr6=peer_ep.get("addr6"),
            kind="wan",
            upstream=link_name,
            routes={
                "ipv4": peer_routes4,
                "ipv6": peer_routes6,
            },
        )
