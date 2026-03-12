# ./clabgen/s88/CM/policy_firewall.py
from __future__ import annotations

from typing import Any, Dict, List


def _proto(match: Dict[str, Any]) -> str | None:
    proto = match.get("proto")
    if proto is None:
        return None
    proto = str(proto).lower()
    if proto == "any":
        return None
    return proto


def _dports(match: Dict[str, Any]) -> List[int]:
    value = match.get("dports")
    if value is None:
        return []

    if isinstance(value, int):
        return [value]

    if isinstance(value, list):
        return [int(v) for v in value]

    raise RuntimeError("invalid dports")


def _rule_for_match(
    src_if: str,
    dst_if: str,
    match: Dict[str, Any],
    action: str,
) -> str:
    proto = _proto(match)
    dports = _dports(match)

    rule = f'nft add rule inet fw forward iifname "{src_if}" oifname "{dst_if}"'

    if proto == "icmp":
        rule += " meta l4proto icmp"
    elif proto:
        rule += f" {proto}"

    if dports:
        if len(dports) == 1:
            rule += f" dport {dports[0]}"
        else:
            ports = ", ".join(str(p) for p in dports)
            rule += f" dport {{ {ports} }}"

    rule += f" {action}"
    return rule


def render(input_data: Dict[str, Any]) -> List[str]:
    zone_interfaces = input_data.get("zone_interfaces", {})
    if not isinstance(zone_interfaces, dict):
        raise RuntimeError("missing firewall zone_interfaces")

    rules = input_data.get("rules", [])
    if not isinstance(rules, list):
        raise RuntimeError("missing firewall rules")

    cmds: List[str] = [
        "echo '[FW] policy firewall starting'",
        "nft add table inet fw",
        "nft 'add chain inet fw forward { type filter hook forward priority 0 ; policy drop ; }'",
        "nft add rule inet fw forward ct state established,related accept",
        "nft add rule inet fw forward ct state invalid drop",
        'nft add rule inet fw forward iifname "eth0" drop',
        'nft add rule inet fw forward oifname "eth0" drop',
    ]

    emitted: set[str] = set()

    for rule_obj in rules:
        if not isinstance(rule_obj, dict):
            continue

        src_zone = rule_obj.get("src_zone")
        dst_zone = rule_obj.get("dst_zone")
        action = "accept" if rule_obj.get("action") == "accept" else "drop"
        matches = rule_obj.get("matches", [])

        if not isinstance(src_zone, str) or not src_zone:
            continue
        if not isinstance(dst_zone, str) or not dst_zone:
            continue
        if not isinstance(matches, list):
            continue

        src_if = zone_interfaces.get(src_zone)
        dst_if = zone_interfaces.get(dst_zone)

        if not isinstance(src_if, str) or not src_if:
            continue
        if not isinstance(dst_if, str) or not dst_if:
            continue

        for match in matches:
            if not isinstance(match, dict):
                continue
            rule = _rule_for_match(src_if, dst_if, match, action)
            if rule not in emitted:
                emitted.add(rule)
                cmds.append(rule)

    cmds.append("nft list table inet fw")

    return cmds
