# ./clabgen/default_routes.py
from __future__ import annotations

from typing import Dict, Any, List, Optional
import ipaddress


def _peer_v4(addr4: str) -> Optional[str]:
    """
    Given an IPv4 interface (e.g. 10.10.0.0/31), return the peer address
    on that P2P network (e.g. 10.10.0.1).
    """
    try:
        ipif = ipaddress.IPv4Interface(addr4)
    except Exception:
        return None

    # Works for /31 and /30, etc. For /31 specifically, there are two usable IPs.
    hosts = list(ipif.network.hosts())
    if len(hosts) < 2:
        return None

    for h in hosts:
        if h != ipif.ip:
            return str(h)

    return None


def _peer_v6(addr6: str) -> Optional[str]:
    """
    Given an IPv6 interface (e.g. fd42:...::/127), return the peer address
    on that P2P network (e.g. fd42:...::1).
    """
    try:
        ipif = ipaddress.IPv6Interface(addr6)
    except Exception:
        return None

    hosts = list(ipif.network.hosts())
    if len(hosts) < 2:
        return None

    for h in hosts:
        if h != ipif.ip:
            return str(h)

    return None


def _has_default_routes_declared(node: Dict[str, Any]) -> bool:
    """
    If the solver explicitly declared default routes, don't synthesize.
    """
    for iface in (node.get("interfaces", {}) or {}).values():
        for r in (iface.get("routes4", []) or []):
            if isinstance(r, dict) and r.get("to") in ("0.0.0.0/0", "default"):
                return True
        for r in (iface.get("routes6", []) or []):
            if isinstance(r, dict) and r.get("to") in ("::/0", "default"):
                return True
    return False


def render_default_routes(node: Dict[str, Any], eth_map: Dict[str, int]) -> List[str]:
    """
    Deterministic ACCESS default-route synthesis.

    This fixes the exact gap you observed: the "working" topology hard-codes:
      - ip route replace default via 10.10.0.1 dev eth1
      - ip -6 route replace default via fd42:...::1 dev eth1

    The "new pipeline" only renders declared routes; ACCESS defaults were never declared,
    so ACCESS kept docker mgmt default instead.

    We only synthesize for ACCESS nodes, determined by:
      - node["role"] containing "access", OR
      - node["name"] ending with "-s-router-access"
    """
    role = str(node.get("role") or "")
    name = str(node.get("name") or "")

    is_access = ("access" in role) or name.endswith("-s-router-access")
    if not is_access:
        return []

    if _has_default_routes_declared(node):
        return []

    interfaces = node.get("interfaces", {}) or {}

    # Pick the first dataplane interface deterministically (sorted by logical ifname),
    # must map to eth>=1 (eth0 is mgmt).
    chosen_if = None
    chosen_eth = None
    chosen_iface = None

    for logical_if in sorted(interfaces.keys()):
        eth = eth_map.get(logical_if)
        if eth is None or eth < 1:
            continue
        chosen_if = logical_if
        chosen_eth = eth
        chosen_iface = interfaces.get(logical_if) or {}
        break

    if chosen_if is None or chosen_eth is None or chosen_iface is None:
        return []

    cmds: List[str] = []

    addr4 = chosen_iface.get("addr4")
    if isinstance(addr4, str) and addr4:
        nh4 = _peer_v4(addr4)
        if nh4:
            cmds.append(f"ip route replace default via {nh4} dev eth{chosen_eth}")

    addr6 = chosen_iface.get("addr6")
    if isinstance(addr6, str) and addr6:
        nh6 = _peer_v6(addr6)
        if nh6:
            cmds.append(f"ip -6 route replace default via {nh6} dev eth{chosen_eth}")

    return cmds
