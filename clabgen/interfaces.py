from typing import Dict, Any, List


def render_interfaces(node: Dict[str, Any], eth_map: Dict[str, int]) -> List[str]:
    cmds: List[str] = []

    interfaces = node.get("interfaces", {})

    for logical_if, iface in interfaces.items():
        if logical_if not in eth_map:
            continue

        eth = f"eth{eth_map[logical_if]}"

        cmds.append(f"ip link set {eth} up")
        cmds.append(f"sysctl -w net.ipv4.conf.{eth}.rp_filter=0")

    return cmds
