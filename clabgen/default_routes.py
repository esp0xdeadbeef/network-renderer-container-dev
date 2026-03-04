from __future__ import annotations

from typing import Dict, Any, List


def _dst(r: Dict[str, Any]) -> str | None:
    return r.get("dst") or r.get("to")


def _via4(r: Dict[str, Any]) -> str | None:
    return r.get("via4") or r.get("via")


def _via6(r: Dict[str, Any]) -> str | None:
    return r.get("via6") or r.get("via")


def render_default_routes(node: Dict[str, Any], eth_map: Dict[str, int]) -> List[str]:
    role = node.get("role", "")
    if role != "s-router-core":
        return []

    cmds: List[str] = []

    for ifname, iface in node.get("interfaces", {}).items():
        eth = eth_map.get(ifname)
        if eth is None:
            continue

        for r in iface.get("routes4", []):
            if _dst(r) == "0.0.0.0/0":
                via = _via4(r)
                if via:
                    cmds.append(f"ip route replace default via {via} dev eth{eth}")

        for r in iface.get("routes6", []):
            if _dst(r) == "::/0":
                via = _via6(r)
                if via:
                    cmds.append(f"ip -6 route replace default via {via} dev eth{eth}")

    return cmds
