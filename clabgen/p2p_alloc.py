# ./clabgen/p2p_alloc.py
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Iterable, List, Set, Tuple


@dataclass(frozen=True)
class P2PLinkAddrs:
    # /31 and /127 networks with deterministic endpoint assignment:
    #   a = network_address
    #   b = network_address + 1
    net4: ipaddress.IPv4Network
    a4: ipaddress.IPv4Interface
    b4: ipaddress.IPv4Interface
    net6: ipaddress.IPv6Network
    a6: ipaddress.IPv6Interface
    b6: ipaddress.IPv6Interface


def _parse_used_nets(
    used_addr4: Iterable[str], used_addr6: Iterable[str]
) -> Tuple[Set[ipaddress.IPv4Network], Set[ipaddress.IPv6Network]]:
    used4: Set[ipaddress.IPv4Network] = set()
    used6: Set[ipaddress.IPv6Network] = set()

    for s in used_addr4:
        if not s:
            continue
        iface = ipaddress.ip_interface(s)
        used4.add(iface.network)

    for s in used_addr6:
        if not s:
            continue
        iface = ipaddress.ip_interface(s)
        used6.add(iface.network)

    return used4, used6


def alloc_p2p_links(
    pool4_cidr: str,
    pool6_cidr: str,
    *,
    count: int,
    used_addr4: Iterable[str] = (),
    used_addr6: Iterable[str] = (),
) -> List[P2PLinkAddrs]:
    """
    Allocate `count` point-to-point links from pools:
      - IPv4: /31
      - IPv6: /127
    Skips any networks already present in used_*.
    Endpoint assignment is deterministic:
      a = first host (network address), b = second host (network+1)
    """
    pool4 = ipaddress.ip_network(pool4_cidr, strict=False)
    pool6 = ipaddress.ip_network(pool6_cidr, strict=False)

    used4, used6 = _parse_used_nets(used_addr4, used_addr6)

    out: List[P2PLinkAddrs] = []

    # Precompute all candidate subnets, in ascending order.
    cand4 = list(pool4.subnets(new_prefix=31))
    cand6 = list(pool6.subnets(new_prefix=127))

    i4 = 0
    i6 = 0

    while len(out) < count:
        if i4 >= len(cand4) or i6 >= len(cand6):
            raise RuntimeError(
                f"Not enough free p2p space in pools to allocate {count} links"
            )

        n4 = cand4[i4]
        n6 = cand6[i6]
        i4 += 1
        i6 += 1

        if n4 in used4 or n6 in used6:
            continue

        a4 = ipaddress.IPv4Interface(f"{n4.network_address}/31")
        b4 = ipaddress.IPv4Interface(f"{ipaddress.IPv4Address(int(n4.network_address) + 1)}/31")
        a6 = ipaddress.IPv6Interface(f"{n6.network_address}/127")
        b6 = ipaddress.IPv6Interface(f"{ipaddress.IPv6Address(int(n6.network_address) + 1)}/127")

        used4.add(n4)
        used6.add(n6)

        out.append(P2PLinkAddrs(net4=n4, a4=a4, b4=b4, net6=n6, a6=a6, b6=b6))

    return out
