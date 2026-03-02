# ./clabgen/isp.py
from __future__ import annotations

from typing import Dict


def ensure_isp_node(rendered_nodes: Dict[str, Dict], full_name: str, _) -> None:
    if full_name in rendered_nodes:
        return

    rendered_nodes[full_name] = {
        "kind": "linux",
        "image": "clab-frr-plus-tooling:latest",
        "network-mode": "none",
        "exec": [],
    }
