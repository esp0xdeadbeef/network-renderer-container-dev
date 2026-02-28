from __future__ import annotations

from typing import Any, Dict


def render_validation_client(*, addr4: str, gw4: str, addr6: str, gw6: str) -> Dict[str, Any]:
    return {
        "exec": [
            "sysctl -w net.ipv4.ip_forward=0",
            "sysctl -w net.ipv6.conf.all.forwarding=0",
            "ip link set eth1 up",
            f"ip addr replace {addr4} dev eth1",
            f"ip -6 addr replace {addr6} dev eth1",
            f"ip route replace 0.0.0.0/0 via {gw4} dev eth1",
            f"ip -6 route replace ::/0 via {gw6} dev eth1",
        ]
    }
