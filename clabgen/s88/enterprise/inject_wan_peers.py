from __future__ import annotations

from typing import Dict, Any, List
import hashlib
import ipaddress

from clabgen.models import SiteModel, NodeModel, InterfaceModel


MAX_NODE_NAME = 32
MAX_IFACE_NAME = 15


def _ip_only(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None

    try:
        return str(ipaddress.ip_interface(value).ip)
    except ValueError:
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            return None


def _route_lists(iface: InterfaceModel) -> Dict[str, List[Dict[str, Any]]]:
    routes = getattr(iface, "routes", {}) or {}
    routes_v4 = routes.get("ipv4", [])
    routes_v6 = routes.get("ipv6", [])

    out_v4: List[Dict[str, Any]] = []
    out_v6: List[Dict[str, Any]] = []

    for route in routes_v4:
        if isinstance(route, dict):
            out_v4.append(dict(route))

    for route in routes_v6:
        if isinstance(route, dict):
            out_v6.append(dict(route))

    return {"v4": out_v4, "v6": out_v6}


def _rewrite_peer_routes(
    local_iface: InterfaceModel,
    local_ep: Dict[str, Any],
    peer_addr4: str | None,
    peer_addr6: str | None,
) -> Dict[str, List[Dict[str, Any]]]:
    routes = _route_lists(local_iface)

    local_addr4 = _ip_only(local_ep.get("addr4")) or _ip_only(getattr(local_iface, "addr4", None))
    local_addr6 = _ip_only(local_ep.get("addr6")) or _ip_only(getattr(local_iface, "addr6", None))
    peer_ip4 = _ip_only(peer_addr4)
    peer_ip6 = _ip_only(peer_addr6)

    for route in routes["v4"]:
        via4 = _ip_only(route.get("via4"))
        if via4 is not None and peer_ip4 is not None and via4 == peer_ip4 and local_addr4 is not None:
            route["via4"] = local_addr4

    for route in routes["v6"]:
        via6 = _ip_only(route.get("via6"))
        if via6 is not None and peer_ip6 is not None and via6 == peer_ip6 and local_addr6 is not None:
            route["via6"] = local_addr6

    return routes


def _short_node(link_name: str, node_name: str, iface_name: str) -> str:
    digest = hashlib.blake2s(
        f"{link_name}:{node_name}:{iface_name}".encode(),
        digest_size=6,
    ).hexdigest()

    name = f"wanp-{digest}"

    if len(name) > MAX_NODE_NAME:
        name = name[:MAX_NODE_NAME]

    return name


def _short_iface(link_name: str) -> str:
    digest = hashlib.blake2s(link_name.encode(), digest_size=4).hexdigest()
    name = f"wan-{digest}"

    if len(name) > MAX_IFACE_NAME:
        name = name[:MAX_IFACE_NAME]

    return name


def inject_emulated_wan_peers(site: SiteModel) -> None:
    new_nodes: Dict[str, NodeModel] = {}

    for link_name, link in list(site.links.items()):
        if getattr(link, "kind", None) != "wan":
            continue

        endpoints = dict(getattr(link, "endpoints", {}) or {})
        if len(endpoints) != 1:
            continue

        local_node_name, local_ep = next(iter(endpoints.items()))

        if not isinstance(local_ep, dict):
            continue

        iface_name = local_ep.get("interface")
        if not isinstance(iface_name, str) or not iface_name:
            continue

        local_node = site.nodes.get(local_node_name)
        if local_node is None:
            continue

        local_iface = local_node.interfaces.get(iface_name)
        if local_iface is None:
            continue

        peer_name = _short_node(link_name, local_node_name, iface_name)

        if peer_name in site.nodes or peer_name in new_nodes:
            continue

        peer_iface = _short_iface(link_name)

        peer_addr4 = local_ep.get("peerAddr4")
        peer_addr6 = local_ep.get("peerAddr6")

        upstream = (
            local_ep.get("uplink")
            or local_ep.get("upstream")
            or getattr(local_iface, "upstream", None)
        )

        routes = _rewrite_peer_routes(local_iface, local_ep, peer_addr4, peer_addr6)

        peer_node = NodeModel(
            name=peer_name,
            role="wan-peer",
            routing_domain=getattr(local_node, "routing_domain", ""),
            interfaces={
                peer_iface: InterfaceModel(
                    name=peer_iface,
                    addr4=peer_addr4 if isinstance(peer_addr4, str) else None,
                    addr6=peer_addr6 if isinstance(peer_addr6, str) else None,
                    kind="wan",
                    upstream=upstream if isinstance(upstream, str) else None,
                    routes={
                        "ipv4": routes["v4"],
                        "ipv6": routes["v6"],
                    },
                )
            },
        )

        new_nodes[peer_name] = peer_node

        link.endpoints[peer_name] = {
            "node": peer_name,
            "interface": peer_iface,
            "addr4": peer_addr4,
            "addr6": peer_addr6,
            "kind": "wan",
            "uplink": upstream,
            "upstream": upstream,
        }

        print(
            "[inject_wan_peers] endpoint created:"
            f" link={link_name}"
            f" local={local_node_name}:{iface_name}"
            f" peer={peer_name}:{peer_iface}"
        )

    site.nodes.update(new_nodes)
