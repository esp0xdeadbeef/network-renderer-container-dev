# FILE: ./clabgen/sysctl.py

from typing import List


def render_sysctls() -> List[str]:
    return [
        "sysctl -w net.ipv4.conf.eth0.forwarding=0",
        "sysctl -w net.ipv6.conf.eth0.forwarding=0",
        "sysctl -w net.ipv4.ip_forward=1",
        "sysctl -w net.ipv6.conf.all.forwarding=1",
        "sysctl -w net.ipv4.conf.all.rp_filter=0",
        "sysctl -w net.ipv4.conf.default.rp_filter=0",
        "sh -c 'for i in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > \"$i\"; done'",
    ]
