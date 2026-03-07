# ./clabgen/s88/enterprise/inject_clients.py
from __future__ import annotations

import hashlib
import ipaddress

from clabgen.models import SiteModel, NodeModel, InterfaceModel


MAX_HOSTNAME = 63


def _short_name(node: str, iface: str) -> str:
    base = f"client-{node}-{iface}"
    if len(base) <= MAX_HOSTNAME:
        return base

    digest = hashlib.blake2s(
        f"{node}:{iface}".encode(),
        digest_size=4,
    ).hexdigest()
    keep = MAX_HOSTNAME - len(digest) - 1
    return f"{base[:keep]}-{digest}"


def _client_addr(router_cidr: str) -> str:
    iface = ipaddress.ip_interface(router_cidr)
    net = iface.network
    router_ip = iface.ip

    for host in net.hosts():
        if host != router_ip:
            return f"{host}/{net.prefixlen}"

    return router_cidr


def inject_clients(site: SiteModel) -> None:
    for node_name, node in list(site.nodes.items()):
        if node.role != "access":
            continue

        for ifname, iface in list(node.interfaces.items()):
            if iface.kind != "tenant":
                continue

            if not iface.addr4:
                continue

            network = ipaddress.ip_interface(iface.addr4).network
            if not isinstance(network, ipaddress.IPv4Network):
                continue

            if network.prefixlen != 24:
                continue

            link = site.links.get(ifname)
            if not link:
                continue

            client_name = _short_name(node_name, ifname)
            if client_name in site.nodes:
                continue

            client_addr = _client_addr(iface.addr4)

            site.nodes[client_name] = NodeModel(
                name=client_name,
                role="client",
                routing_domain=node.routing_domain,
                interfaces={
                    ifname: InterfaceModel(
                        name=ifname,
                        addr4=client_addr,
                        kind="tenant",
                        upstream=ifname,
                        routes={
                            "ipv4": [
                                {
                                    "dst": "0.0.0.0/0",
                                    "via4": str(ipaddress.ip_interface(iface.addr4).ip),
                                }
                            ],
                            "ipv6": [],
                        },
                    )
                },
            )

            link.endpoints[client_name] = {
                "node": client_name,
                "interface": ifname,
                "addr4": client_addr,
            }
