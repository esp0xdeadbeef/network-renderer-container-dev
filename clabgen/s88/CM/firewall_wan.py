from __future__ import annotations

from typing import Dict, Any, List


def _render_for_interface(wan_if: str) -> List[str]:
    return [
        "nft flush ruleset",
        "nft add table inet filter",
        "nft 'add chain inet filter input { type filter hook input priority 0 ; policy drop ; }'",
        "nft 'add chain inet filter forward { type filter hook forward priority 0 ; policy accept ; }'",
        "nft 'add chain inet filter output { type filter hook output priority 0 ; policy accept ; }'",
        "nft add rule inet filter input iif lo accept",
        "nft add rule inet filter input ct state established,related accept",
        "nft add rule inet filter input ct state invalid drop",
        "nft add rule inet filter input meta l4proto ipv6-icmp accept",
        f'nft add rule inet filter input iifname "{wan_if}" ip saddr {{ 0.0.0.0/8,10.0.0.0/8,100.64.0.0/10,127.0.0.0/8,169.254.0.0/16,172.16.0.0/12,192.168.0.0/16,224.0.0.0/4,240.0.0.0/4 }} drop',
        f'nft add rule inet filter input iifname "{wan_if}" ip6 saddr {{ ::1,fc00::/7,fe80::/10 }} drop',
        f'nft add rule inet filter input iifname != "{wan_if}" tcp dport 22 accept',
        "nft add rule inet filter forward ct state established,related accept",
        "nft add rule inet filter forward ct state invalid drop",
        f'nft add rule inet filter forward iifname "{wan_if}" ip saddr {{ 10.0.0.0/8,100.64.0.0/10,172.16.0.0/12,192.168.0.0/16 }} drop',
        f'nft add rule inet filter forward iifname "{wan_if}" ip6 saddr fc00::/7 drop',
        "nft add table ip nat",
        "nft 'add chain ip nat postrouting { type nat hook postrouting priority srcnat ; policy accept ; }'",
        f'nft add rule ip nat postrouting ip saddr {{ 10.0.0.0/8,172.16.0.0/12,192.168.0.0/16 }} oifname "{wan_if}" masquerade',
        "nft add table inet mangle",
        "nft 'add chain inet mangle forward { type filter hook forward priority mangle ; policy accept ; }'",
        f'nft add rule inet mangle forward oifname "{wan_if}" tcp flags syn tcp option maxseg size set rt mtu',
    ]


def render(input_data: Dict[str, Any]) -> List[str]:
    wan_interfaces = input_data.get("wan_interfaces", [])
    if not isinstance(wan_interfaces, list):
        return []

    cmds: List[str] = []
    first = True

    for wan_if in wan_interfaces:
        if not isinstance(wan_if, str) or not wan_if:
            continue
        if first:
            cmds.extend(_render_for_interface(wan_if))
            first = False
            continue

        cmds.extend(
            [
                f'nft add rule inet filter input iifname "{wan_if}" ip saddr {{ 0.0.0.0/8,10.0.0.0/8,100.64.0.0/10,127.0.0.0/8,169.254.0.0/16,172.16.0.0/12,192.168.0.0/16,224.0.0.0/4,240.0.0.0/4 }} drop',
                f'nft add rule inet filter input iifname "{wan_if}" ip6 saddr {{ ::1,fc00::/7,fe80::/10 }} drop',
                f'nft add rule inet filter input iifname != "{wan_if}" tcp dport 22 accept',
                f'nft add rule inet filter forward iifname "{wan_if}" ip saddr {{ 10.0.0.0/8,100.64.0.0/10,172.16.0.0/12,192.168.0.0/16 }} drop',
                f'nft add rule inet filter forward iifname "{wan_if}" ip6 saddr fc00::/7 drop',
                f'nft add rule ip nat postrouting ip saddr {{ 10.0.0.0/8,172.16.0.0/12,192.168.0.0/16 }} oifname "{wan_if}" masquerade',
                f'nft add rule inet mangle forward oifname "{wan_if}" tcp flags syn tcp option maxseg size set rt mtu',
            ]
        )

    return cmds
