# FILE: ./clabgen/nodes.py

from typing import Dict, Any

from .linux_router import render_linux_router
from .internet_responder import render_internet_responder
from .models import NodeModel


def _model_to_dict(node: NodeModel) -> Dict[str, Any]:
    interfaces: Dict[str, Any] = {}

    for name, iface in node.interfaces.items():
        interfaces[name] = {
            "name": iface.name,
            "addr4": iface.addr4,
            "addr6": iface.addr6,
            "ll6": iface.ll6,
            "routes4": iface.routes4,
            "routes6": iface.routes6,
            "kind": iface.kind,
            "upstream": iface.upstream,
        }

    return {
        "name": node.name,
        "role": node.role,
        "routing_domain": node.routing_domain,
        "interfaces": interfaces,
        "containers": list(node.containers),
    }


def render_node(node: NodeModel, eth_map: Dict[str, int]) -> Dict[str, Any]:
    node_dict = _model_to_dict(node)

    if node.role == "internet-responder":
        rendered = render_internet_responder(node_dict["name"])
    else:
        rendered = render_linux_router(node_dict, eth_map)

    # containerlab node definition must contain ONLY supported fields
    return {
        "exec": rendered.get("exec", []),
    }
