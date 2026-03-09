# ./clabgen/s88/CM/forwarding.py
from __future__ import annotations

from typing import List, Dict, Any


def render(role: str, node_name: str, node_data: Dict[str, Any]) -> List[str]:
    _ = node_name
    _ = node_data

    if role in {"core", "policy", "upstream-selector", "wan-peer", "isp"}:
        cmds = [
            "sysctl -w net.ipv4.ip_forward=1",
            "sysctl -w net.ipv6.conf.all.forwarding=1",
        ]

        if role not in {"wan-peer", "isp"}:
            cmds.extend(
                [
                    "sysctl -w net.ipv4.conf.eth0.forwarding=0",
                    "sysctl -w net.ipv6.conf.eth0.forwarding=0",
                ]
            )

        return cmds

    return []
