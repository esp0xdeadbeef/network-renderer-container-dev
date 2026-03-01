from __future__ import annotations

from typing import Dict

from .models import NodeModel


def _iface_config(iface, ifname: str) -> str:
    lines = [f"auto {ifname}", f"iface {ifname} inet static"]

    if iface.addr4:
        lines.append(f"    address {iface.addr4}")

    lines.append(f"iface {ifname} inet6 static")

    if iface.addr6:
        lines.append(f"    address {iface.addr6}")

    if iface.ll6:
        lines.append(f"    up ip -6 addr add {iface.ll6} dev {ifname}")

    return "\n".join(lines)


def render_node(node: NodeModel, eth_map: Dict[str, int]) -> Dict:
    exec_cmds = []
    network_cfg_lines = []

    for link_name, iface in node.interfaces.items():
        if link_name not in eth_map:
            continue

        eth = eth_map[link_name]
        ifname = f"eth{eth}"

        network_cfg_lines.append(_iface_config(iface, ifname))

        for route in iface.routes4:
            dst = route.get("dst")
            via = route.get("via4")
            if dst and via:
                exec_cmds.append(f"ip route add {dst} via {via} dev {ifname}")
            elif dst:
                exec_cmds.append(f"ip route add {dst} dev {ifname}")

        for route in iface.routes6:
            dst = route.get("dst")
            via = route.get("via6")
            if dst and via:
                exec_cmds.append(f"ip -6 route add {dst} via {via} dev {ifname}")
            elif dst:
                exec_cmds.append(f"ip -6 route add {dst} dev {ifname}")

    return {
        "kind": "linux",
        "image": "frrouting/frr:latest",
        "network-mode": "none",
        "exec": exec_cmds,
    }
