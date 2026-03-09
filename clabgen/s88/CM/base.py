# clabgen/s88/CM/base.py
from __future__ import annotations

from typing import Callable, Dict, List, Any

from .empty import render as render_empty
from .forwarding import render as render_forwarding
from .nat import render as render_nat
from .firewall import render as render_firewall


CM_BY_ROLE: Dict[str, List[Callable[[str, str, Dict[str, Any]], List[str]]]] = {
    "access": [render_empty],
    "client": [render_empty],
    "core": [render_forwarding],
    "policy": [render_forwarding, render_firewall],
    "upstream-selector": [render_forwarding],
    "wan-peer": [render_forwarding, render_nat],
    "isp": [render_forwarding],
}


def render(role: str, node_name: str, node_data: Dict[str, Any]) -> List[str]:
    if role not in CM_BY_ROLE:
        raise ValueError(f"No CM mapping for role={role!r} node={node_name!r}")

    cmds: List[str] = []
    for fn in CM_BY_ROLE[role]:
        cmds.extend(fn(role, node_name, node_data))
    return cmds
