# ./generate-clab-config.py
#!/usr/bin/env python3

import sys
import json
from pathlib import Path
from typing import List, Dict, Any

DEFAULT_SOLVER_JSON = "output-network-solver.json"
DEFAULT_TOPO_FILE = "fabric.clab.yml"
IMAGE = "frrouting/frr:latest"

ISP_CORE_V4 = "203.0.113.1/30"
ISP_CORE_V6 = "2001:db8:ffff::1/48"
ISP_ISP_V4 = "203.0.113.2/30"
ISP_ISP_V6 = "2001:db8:ffff::2/48"


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def load_solver(path: Path) -> Dict[str, Any]:
    if not path.exists():
        fail(f"Solver JSON not found: {path}")
    with path.open() as f:
        return json.load(f)


def get_required(d: Dict[str, Any], path: List[str], desc: str):
    cur = d
    for p in path:
        if p not in cur:
            fail(f"Missing required solver field: {desc}")
        cur = cur[p]
    return cur


def tenant_gateway_v4(cidr: str) -> str:
    parts = cidr.split("/")[0].split(".")
    return f"{parts[0]}.{parts[1]}.{parts[2]}.1"


def tenant_ip_v4(cidr: str) -> str:
    parts = cidr.split("/")[0].split(".")
    return f"{parts[0]}.{parts[1]}.{parts[2]}.2/24"


def tenant_gateway_v6(cidr: str) -> str:
    return cidr.replace("::/64", "::1")


def tenant_ip_v6(cidr: str) -> str:
    return cidr.replace("::/64", "::2/64")


def emit_routes(data, node: str, iface: str, version: int) -> List[str]:
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


def emit_default(data, node: str, iface: str, version: int) -> str:
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


def main():
    solver_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_SOLVER_JSON)
    topo_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(DEFAULT_TOPO_FILE)

    data = load_solver(solver_path)

    assumptions = get_required(
        data, ["site", "_routingMaps", "assumptions"], "routing assumptions"
    )

    core = assumptions["core"]
    policy = assumptions["policy"]
    access = assumptions["singleAccess"]
    upsel = assumptions["upstreamSelector"]

    tenants_v4 = data["site"]["_routingMaps"]["tenants"]["ipv4"]
    tenants_v6 = data["site"]["_routingMaps"]["tenants"]["ipv6"]

    client_tenant_v4 = next(
        t["ipv4"]
        for t in data["site"]["compilerIR"]["domains"]["tenants"]
        if t["name"] == "clients"
    )
    client_tenant_v6 = next(
        t["ipv6"]
        for t in data["site"]["compilerIR"]["domains"]["tenants"]
        if t["name"] == "clients"
    )

    access_if = "p2p-s-router-access-s-router-policy"
    policy_if_up = "p2p-s-router-policy-s-router-upstream-selector"
    policy_if_access = "p2p-s-router-access-s-router-policy"
    upsel_if = "p2p-s-router-policy-s-router-upstream-selector"
    core_if = "p2p-s-router-core-s-router-upstream-selector"

    access_def4 = emit_default(data, access, access_if, 4)
    access_def6 = emit_default(data, access, access_if, 6)
    policy_def4 = emit_default(data, policy, policy_if_up, 4)
    policy_def6 = emit_default(data, policy, policy_if_up, 6)
    upsel_def4 = emit_default(data, upsel, core_if, 4)
    upsel_def6 = emit_default(data, upsel, core_if, 6)

    client_gw_v4 = tenant_gateway_v4(client_tenant_v4)
    client_ip_v4 = tenant_ip_v4(client_tenant_v4)
    client_gw_v6 = tenant_gateway_v6(client_tenant_v6)
    client_ip_v6 = tenant_ip_v6(client_tenant_v6)

    nodes = {}

    def base_exec():
        return [
            "sysctl -w net.ipv4.ip_forward=1",
            "sysctl -w net.ipv6.conf.all.forwarding=1",
        ]

    nodes[access] = {
        "exec": base_exec()
        + [
            "ip link set eth1 up",
            f"ip addr replace {data['site']['links'][access_if]['endpoints'][access]['addr4']} dev eth1",
            f"ip -6 addr replace {data['site']['links'][access_if]['endpoints'][access]['addr6']} dev eth1",
            "ip link set eth2 up",
            f"ip addr replace {client_gw_v4}/24 dev eth2",
            f"ip -6 addr replace {client_gw_v6}/64 dev eth2",
            f"ip route replace default via {access_def4}",
            f"ip -6 route replace default via {access_def6}",
        ],
    }

    nodes[policy] = {
        "exec": base_exec()
        + [
            "ip link set eth1 up",
            "ip link set eth2 up",
            f"ip addr replace {data['site']['links'][access_if]['endpoints'][policy]['addr4']} dev eth1",
            f"ip -6 addr replace {data['site']['links'][access_if]['endpoints'][policy]['addr6']} dev eth1",
            f"ip addr replace {data['site']['links'][policy_if_up]['endpoints'][policy]['addr4']} dev eth2",
            f"ip -6 addr replace {data['site']['links'][policy_if_up]['endpoints'][policy]['addr6']} dev eth2",
        ]
        + emit_routes(data, policy, policy_if_access, 4)
        + emit_routes(data, policy, policy_if_access, 6)
        + [
            f"ip route replace default via {policy_def4}",
            f"ip -6 route replace default via {policy_def6}",
        ],
    }

    nodes[upsel] = {
        "exec": base_exec()
        + [
            "ip link set eth1 up",
            "ip link set eth2 up",
            f"ip addr replace {data['site']['links'][core_if]['endpoints'][upsel]['addr4']} dev eth1",
            f"ip -6 addr replace {data['site']['links'][core_if]['endpoints'][upsel]['addr6']} dev eth1",
            f"ip addr replace {data['site']['links'][upsel_if]['endpoints'][upsel]['addr4']} dev eth2",
            f"ip -6 addr replace {data['site']['links'][upsel_if]['endpoints'][upsel]['addr6']} dev eth2",
        ]
        + emit_routes(data, upsel, upsel_if, 4)
        + emit_routes(data, upsel, upsel_if, 6)
        + [
            f"ip route replace default via {upsel_def4}",
            f"ip -6 route replace default via {upsel_def6}",
        ],
    }

    nodes[core] = {
        "exec": base_exec()
        + [
            "ip link set eth1 up",
            f"ip addr replace {data['site']['links'][core_if]['endpoints'][core]['addr4']} dev eth1",
            f"ip -6 addr replace {data['site']['links'][core_if]['endpoints'][core]['addr6']} dev eth1",
            "ip link set eth2 up",
            f"ip addr replace {ISP_CORE_V4} dev eth2",
            f"ip -6 addr replace {ISP_CORE_V6} dev eth2",
        ]
        + emit_routes(data, core, core_if, 4)
        + emit_routes(data, core, core_if, 6)
        + [
            "ip route replace default via 203.0.113.2",
            "ip -6 route replace default via 2001:db8:ffff::2",
        ],
    }

    nodes["isp"] = {
        "exec": base_exec()
        + [
            "ip link set eth1 up",
            f"ip addr replace {ISP_ISP_V4} dev eth1",
            f"ip -6 addr replace {ISP_ISP_V6} dev eth1",
        ]
        + [f"ip route replace {v4} via 203.0.113.1" for v4 in tenants_v4]
        + [f"ip -6 route replace {v6} via 2001:db8:ffff::1" for v6 in tenants_v6],
    }

    nodes["client"] = {
        "exec": [
            "ip link set eth1 up",
            f"ip addr replace {client_ip_v4} dev eth1",
            f"ip -6 addr replace {client_ip_v6} dev eth1",
            f"ip route replace default via {client_gw_v4}",
            f"ip -6 route replace default via {client_gw_v6}",
        ]
    }

    topology = {
        "name": "fabric",
        "topology": {
            "defaults": {
                "kind": "linux",
                "image": IMAGE,
                "network-mode": "none",
                "sysctls": {
                    "net.ipv4.ip_forward": "1",
                    "net.ipv6.conf.all.forwarding": "1",
                    "net.ipv4.conf.default.rp_filter": "0",
                },
            },
            "nodes": nodes,
            "links": [
                {"endpoints": [f"{access}:eth1", f"{policy}:eth1"]},
                {"endpoints": [f"{policy}:eth2", f"{upsel}:eth2"]},
                {"endpoints": [f"{core}:eth1", f"{upsel}:eth1"]},
                {"endpoints": [f"{core}:eth2", "isp:eth1"]},
                {"endpoints": [f"{access}:eth2", "client:eth1"]},
            ],
        },
    }

    import yaml

    with topo_path.open("w") as f:
        yaml.dump(topology, f, sort_keys=False)


if __name__ == "__main__":
    main()
