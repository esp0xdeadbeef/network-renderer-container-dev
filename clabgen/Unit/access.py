from __future__ import annotations

from typing import Dict, Any

from clabgen.models import NodeModel
from clabgen.Unit.common import render_linux_node


def render(node_name: str, node: NodeModel, eth_map: Dict[str, int]) -> Dict[str, Any]:
    return render_linux_node(
        node_name=node_name,
        node=node,
        eth_map=eth_map,
    )
