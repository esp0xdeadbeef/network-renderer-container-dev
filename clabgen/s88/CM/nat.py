# ./clabgen/s88/CM/nat.py
from __future__ import annotations

from typing import List, Dict, Any


def render(input_data: Dict[str, Any]) -> List[str]:
    wan_interface = input_data.get("wan_interface")
    if not isinstance(wan_interface, str) or not wan_interface:
        return []

    return [
        "nft flush ruleset",
        "nft add table ip nat",
        "nft 'add chain ip nat postrouting { type nat hook postrouting priority 100 ; }'",
        f'nft add rule ip nat postrouting oifname "{wan_interface}" masquerade',
        "ip route flush cache",
        "ip -6 route flush cache",
    ]
