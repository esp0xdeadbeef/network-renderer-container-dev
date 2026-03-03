# FILE: ./clabgen/linux_router.py

from typing import Dict, Any, List

from .sysctl import render_sysctls
from .interfaces import render_interfaces
from .addressing import render_addressing
from .connected_routes import render_connected_routes
from .static_routes import render_static_routes
from .default_routes import render_default_routes


def render_linux_router(node: Dict[str, Any], eth_map: Dict[str, int]) -> Dict[str, Any]:
    exec_cmds: List[str] = []

    exec_cmds += render_sysctls()
    exec_cmds += render_interfaces(node, eth_map)
    exec_cmds += render_addressing(node, eth_map)
    exec_cmds += render_connected_routes(node, eth_map)
    exec_cmds += render_static_routes(node, eth_map)
    exec_cmds += render_default_routes(node, eth_map)

    return {
        "exec": exec_cmds,
    }
