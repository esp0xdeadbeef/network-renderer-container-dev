from typing import Dict, Any, List
import ipaddress


def _network_from_addr(addr: str) -> str:
    return str(ipaddress.ip_interface(addr).network)


def _is_network_base(addr: str) -> bool:
    iface = ipaddress.ip_interface(addr)
    return iface.ip == iface.network.network_address


def render_connected_routes(node: Dict[str, Any], eth_map: Dict[str, int]) -> List[str]:
    cmds: List[str] = []

    interfaces = node.get("interfaces", {})

    for logical_if, iface in interfaces.items():
        if logical_if not in eth_map:
            continue

        eth = f"eth{eth_map[logical_if]}"

        addr4 = iface.get("addr4")
        if addr4 and _is_network_base(addr4):
            net4 = _network_from_addr(addr4)
            cmds.append(f"ip route replace {net4} dev {eth} scope link")

        addr6 = iface.get("addr6")
        if addr6 and _is_network_base(addr6):
            net6 = _network_from_addr(addr6)
            cmds.append(f"ip -6 route replace {net6} dev {eth}")

    return cmds
