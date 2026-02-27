# ./clabgen/routes.py
from typing import List, Dict, Any


def emit_routes(data: Dict[str, Any], node: str, iface: str, version: int) -> List[str]:
    routes = (
        data["site"]["nodes"]
        .get(node, {})
        .get("interfaces", {})
        .get(iface, {})
        .get(f"routes{version}", [])
    )
    cmds = []
    for r in routes:
        if version == 4:
            if r["dst"] != "0.0.0.0/0":
                cmds.append(f"ip route replace {r['dst']} via {r['via4']}")
        else:
            if r["dst"] != "::/0":
                cmds.append(f"ip -6 route replace {r['dst']} via {r['via6']}")
    return cmds


def emit_default(data: Dict[str, Any], node: str, iface: str, version: int) -> str:
    routes = (
        data["site"]["nodes"]
        .get(node, {})
        .get("interfaces", {})
        .get(iface, {})
        .get(f"routes{version}", [])
    )
    for r in routes:
        if (version == 4 and r["dst"] == "0.0.0.0/0") or (
            version == 6 and r["dst"] == "::/0"
        ):
            return r[f"via{version}"]
    return ""
