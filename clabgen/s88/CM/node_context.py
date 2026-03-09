from __future__ import annotations
from typing import Dict, Any


def build_node_context(
    model: Dict[str, Any],
    node_name: str,
    node_data: Dict[str, Any],
    node_links: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build renderer context for node role renderers.
    """

    ctx: Dict[str, Any] = {}

    ctx["node_name"] = node_name
    ctx["node"] = node_data
    ctx["_s88_links"] = node_links

    #
    # CRITICAL: pass enterprise contract model
    #
    ctx["enterprise"] = model.get("enterprise", {})

    return ctx
