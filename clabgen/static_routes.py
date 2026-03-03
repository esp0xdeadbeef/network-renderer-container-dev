# ./clabgen/static_routes.py
from typing import Dict, Any, List
import ipaddress


def _ipv4_interface_network(addr_cidr: str) -> ipaddress.IPv4Network:
    return ipaddress.IPv4Interface(addr_cidr).network


def _ipv6_interface_network(addr_cidr: str) -> ipaddress.IPv6Network:
    return ipaddress.IPv6Interface(addr_cidr).network


def _strip_prefix(v: str) -> str:
    """
    Accept solver outputs like:
      - "10.10.0.1/31"
      - "fd42:dead:beef:1000::1/127"
    and normalize them to a plain IP string.

    If the value is weird, return original and let validators reject it.
    """
    if not isinstance(v, str):
        return ""
    v = v.strip()
    if not v:
        return ""
    if "/" in v:
        return v.split("/", 1)[0].strip()
    return v


def _collect_ipv4_connected_networks(node: Dict[str, Any]) -> List[ipaddress.IPv4Network]:
    nets: List[ipaddress.IPv4Network] = []

    for iface in node.get("interfaces", {}).values():
        addrs: List[str] = []

        a4_list = iface.get("addresses4", [])
        if isinstance(a4_list, list):
            addrs.extend([a for a in a4_list if isinstance(a, str)])

        a4 = iface.get("addr4")
        if isinstance(a4, str) and a4:
            addrs.append(a4)

        for addr in addrs:
            try:
                nets.append(_ipv4_interface_network(addr))
            except Exception:
                continue

    return nets


def _collect_ipv6_connected_networks(node: Dict[str, Any]) -> List[ipaddress.IPv6Network]:
    nets: List[ipaddress.IPv6Network] = []

    for iface in node.get("interfaces", {}).values():
        addrs: List[str] = []

        a6_list = iface.get("addresses6", [])
        if isinstance(a6_list, list):
            addrs.extend([a for a in a6_list if isinstance(a, str)])

        a6 = iface.get("addr6")
        if isinstance(a6, str) and a6:
            addrs.append(a6)

        for addr in addrs:
            try:
                nets.append(_ipv6_interface_network(addr))
            except Exception:
                continue

    return nets


def _is_valid_ipv4_nexthop(nh: str, connected: List[ipaddress.IPv4Network]) -> bool:
    nh = _strip_prefix(nh)
    if not nh:
        return False

    try:
        ip = ipaddress.IPv4Address(nh)
    except Exception:
        return False

    for net in connected:
        if ip in net:
            return True

    return False


def _is_valid_ipv6_nexthop(nh: str, connected: List[ipaddress.IPv6Network]) -> bool:
    nh = _strip_prefix(nh)
    if not nh:
        return False

    try:
        ip = ipaddress.IPv6Address(nh)
    except Exception:
        return False

    for net in connected:
        if ip in net:
            return True

    return False


def render_static_routes(node: Dict[str, Any], eth_map: Dict[str, int]) -> List[str]:
    cmds: List[str] = []

    connected_v4 = _collect_ipv4_connected_networks(node)
    connected_v6 = _collect_ipv6_connected_networks(node)

    for ifname, iface in node.get("interfaces", {}).items():
        eth = eth_map.get(ifname)
        if eth is None:
            continue

        # IPv4
        for r in iface.get("routes4", []):
            if not isinstance(r, dict):
                continue

            via = r.get("via")
            dst = r.get("to")

            if not isinstance(via, str) or not isinstance(dst, str):
                continue
            if not via or not dst:
                continue

            if not _is_valid_ipv4_nexthop(via, connected_v4):
                continue

            cmds.append(f"ip route replace {dst} via {_strip_prefix(via)} dev eth{eth}")

        # IPv6
        for r in iface.get("routes6", []):
            if not isinstance(r, dict):
                continue

            via = r.get("via")
            dst = r.get("to")

            if not isinstance(via, str) or not isinstance(dst, str):
                continue
            if not via or not dst:
                continue

            if not _is_valid_ipv6_nexthop(via, connected_v6):
                continue

            cmds.append(f"ip -6 route replace {dst} via {_strip_prefix(via)} dev eth{eth}")

    return cmds
