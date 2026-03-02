# FILE: ./clabgen/internet_responder.py

from typing import Dict, Any, List


def render_internet_responder(name: str) -> Dict[str, Any]:
    exec_cmds: List[str] = [
        "sysctl -w net.ipv4.conf.eth0.forwarding=0",
        "sysctl -w net.ipv6.conf.eth0.forwarding=0",
        "sysctl -w net.ipv4.ip_forward=1",
        "sysctl -w net.ipv6.conf.all.forwarding=1",
        "sysctl -w net.ipv4.conf.all.rp_filter=0",
        "sysctl -w net.ipv4.conf.default.rp_filter=0",
        "sh -c 'for i in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > \"$i\"; done'",
        "ip link set eth1 up",
        "ip route replace default dev eth1",
        "ip -6 route replace default dev eth1",
    ]

    return {
        "exec": exec_cmds,
    }
