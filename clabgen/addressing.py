from typing import Dict, Any, List
import ipaddress


def _canon_v6(addr: str) -> str:
    """
    Normalize IPv6 addresses so they always render as compressed form.

    Example:
        fd42:dead:beef:1000:0:0:0:0/127
    becomes
        fd42:dead:beef:1000::/127
    """
    try:
        return str(ipaddress.IPv6Interface(addr))
    except Exception:
        return addr


def render_addressing(node: Dict[str, Any], eth_map: Dict[str, int]) -> List[str]:
    cmds: List[str] = []

    for ifname, iface in node.get("interfaces", {}).items():
        eth = eth_map.get(ifname)
        if eth is None:
            continue

        addr4 = iface.get("addr4")
        addr6 = iface.get("addr6")

        if isinstance(addr4, str) and addr4:
            cmds.append(f"ip addr replace {addr4} dev eth{eth}")

        if isinstance(addr6, str) and addr6:
            addr6 = _canon_v6(addr6)
            cmds.append(f"ip -6 addr replace {addr6} dev eth{eth}")

    return cmds
