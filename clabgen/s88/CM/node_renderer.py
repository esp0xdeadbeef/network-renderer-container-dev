from __future__ import annotations

from typing import Dict, Any, List

from clabgen.s88.CM import firewall


def render_node_exec(
    model: Dict[str, Any],
    node_name: str,
    node_data: Dict[str, Any],
    node_links: Dict[str, Any],
) -> List[str]:
    _ = model
    _ = node_name
    _ = node_links

    cm_inputs = node_data.get("cm_inputs", {})
    if not isinstance(cm_inputs, dict):
        cm_inputs = {}

    exec_cmds: List[str] = []
    firewall_input = cm_inputs.get("firewall", {})
    if isinstance(firewall_input, dict):
        exec_cmds.extend(firewall.render(firewall_input))

    return exec_cmds
