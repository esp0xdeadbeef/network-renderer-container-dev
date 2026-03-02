from typing import Dict, Any, List


def _route4(dst: str, via: str | None, dev: str) -> str:
    if dst == "0.0.0.0/0":
        if via:
            return f"ip route replace default via {via} dev {dev}"
        return f"ip route replace default dev {dev}"

    if via:
        return f"ip route replace {dst} via {via} dev {dev}"

    return f"ip route replace {dst} dev {dev}"


def _route6(dst: str, via: str | None, dev: str) -> str:
    if dst == "::/0":
        if via:
            return f"ip -6 route replace default via {via} dev {dev}"
        return f"ip -6 route replace default dev {dev}"

    if via:
        return f"ip -6 route replace {dst} via {via} dev {dev}"

    return f"ip -6 route replace {dst} dev {dev}"


def render_static_routes(node: Dict[str, Any], eth_map: Dict[str, int]) -> List[str]:
    cmds: List[str] = []

    interfaces = node.get("interfaces", {})

    for logical_if, iface in interfaces.items():
        if logical_if not in eth_map:
            continue

        eth = f"eth{eth_map[logical_if]}"

        for r in iface.get("routes4", []):
            dst = r.get("dst")
            via = r.get("via4")
            if dst:
                cmds.append(_route4(dst, via, eth))

        for r in iface.get("routes6", []):
            dst = r.get("dst")
            via = r.get("via6")
            if dst:
                cmds.append(_route6(dst, via, eth))

    return cmds
