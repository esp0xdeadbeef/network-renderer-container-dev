from typing import Dict, Any, List


def render_addressing(node: Dict[str, Any], eth_map: Dict[str, int]) -> List[str]:
    cmds: List[str] = []

    interfaces = node.get("interfaces", {})

    for logical_if, iface in interfaces.items():
        if logical_if not in eth_map:
            continue

        eth = f"eth{eth_map[logical_if]}"

        addr4 = iface.get("addr4")
        addr6 = iface.get("addr6")

        if addr4:
            cmds.append(f"ip addr replace {addr4} dev {eth}")

        if addr6:
            cmds.append(f"ip -6 addr replace {addr6} dev {eth}")

    return cmds
