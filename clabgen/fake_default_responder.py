# FILE: ./clabgen/fake_default_responder.py
from __future__ import annotations

from typing import List


def fake_default_responder_exec() -> List[str]:
    # Make the kernel treat *any* destination as local and answer pings for validation.
    # IPv4: "local 0.0.0.0/0 dev lo"
    # IPv6: "local ::/0 dev lo"
    return [
        "sysctl -w net.ipv4.ip_forward=1",
        "sysctl -w net.ipv6.conf.all.forwarding=1",
        "sysctl -w net.ipv4.conf.all.rp_filter=0",
        "sysctl -w net.ipv4.conf.default.rp_filter=0",
        "ip route replace local 0.0.0.0/0 dev lo",
        "ip -6 route replace local ::/0 dev lo",
    ]
