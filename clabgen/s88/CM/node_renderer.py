from __future__ import annotations

from typing import Dict, Any, List

from clabgen.s88.CM.node_context import build_node_context
from clabgen.s88.CM import firewall


def render_node_exec(
    model: Dict[str, Any],
    node_name: str,
    node_data: Dict[str, Any],
    node_links: Dict[str, Any],
) -> List[str]:

    role = node_data.get("role")

    node_ctx = build_node_context(
        model=model,
        node_name=node_name,
        node_data=node_data,
        node_links=node_links,
    )

    exec_cmds: List[str] = []

    exec_cmds.extend(
        firewall.render(
            role=role,
            node_name=node_name,
            node_data=node_ctx,
        )
    )

    return exec_cmds
