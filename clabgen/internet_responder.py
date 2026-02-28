# FILE: ./clabgen/internet_responder.py
from typing import Dict, Any


def render_internet_responder(name: str) -> Dict[str, Any]:
    return {
        "kind": "linux",
        "image": "frrouting/frr:latest",
        "exec": [
            "sysctl -w net.ipv4.ip_forward=1",
            "sysctl -w net.ipv6.conf.all.forwarding=1",
            "ip link set eth1 up",
            "ip addr replace 10.255.255.1/24 dev eth1",
            "ip -6 addr replace fd42:ffff::1/64 dev eth1",
            "ip route replace 0.0.0.0/0 dev eth1",
            "ip -6 route replace ::/0 dev eth1",
        ],
    }
