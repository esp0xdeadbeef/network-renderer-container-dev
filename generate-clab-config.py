# ./generate-clab-config.py
#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Allow imports from the repo checkout even when executed from /nix/store
sys.path.insert(0, str(Path.cwd()))

import yaml  # type: ignore

from clabgen.solver import load_solver, get_required
from clabgen.addressing import (
    tenant_gateway_v4,
    tenant_gateway_v6,
    tenant_host_ip_v4,
    tenant_host_ip_v6,
)
from clabgen.routes import emit_routes, emit_default
from clabgen.p2p_alloc import alloc_p2p_links

DEFAULT_SOLVER_JSON = "output-network-solver.json"
DEFAULT_TOPO_FILE = "fabric.clab.yml"
IMAGE = "frrouting/frr:latest"

ISP_CORE_V4 = "203.0.113.1/30"
ISP_CORE_V6 = "2001:db8:ffff::1/48"
ISP_ISP_V4 = "203.0.113.2/30"
ISP_ISP_V6 = "2001:db8:ffff::2/48"


def _base_exec() -> List[str]:
    return [
        "sysctl -w net.ipv4.ip_forward=1",
        "sysctl -w net.ipv6.conf.all.forwarding=1",
    ]


def _gather_used_p2p_addrs(data: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    used4: List[str] = []
    used6: List[str] = []
    for link in (data.get("site", {}).get("links", {}) or {}).values():
        eps = (link or {}).get("endpoints", {}) or {}
        for ep in eps.values():
            if not isinstance(ep, dict):
                continue
            a4 = ep.get("addr4")
            a6 = ep.get("addr6")
            if isinstance(a4, str) and a4:
                used4.append(a4)
            if isinstance(a6, str) and a6:
                used6.append(a6)
    return used4, used6


def main() -> None:
    solver_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_SOLVER_JSON)
    topo_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(DEFAULT_TOPO_FILE)

    data = load_solver(solver_path)

    assumptions = get_required(
        data, ["site", "_routingMaps", "assumptions"], "routing assumptions"
    )

    core = assumptions["core"]
    policy = assumptions["policy"]
    access_base = assumptions["singleAccess"]
    upsel = assumptions["upstreamSelector"]

    tenants_v4 = data["site"]["_routingMaps"]["tenants"]["ipv4"]
    tenants_v6 = data["site"]["_routingMaps"]["tenants"]["ipv6"]
    tenant_domains = data["site"]["compilerIR"]["domains"]["tenants"]

    policy_if_up = "p2p-s-router-policy-s-router-upstream-selector"
    upsel_if = "p2p-s-router-policy-s-router-upstream-selector"
    core_if = "p2p-s-router-core-s-router-upstream-selector"

    policy_def4 = emit_default(data, policy, policy_if_up, 4)
    policy_def6 = emit_default(data, policy, policy_if_up, 6)
    upsel_def4 = emit_default(data, upsel, core_if, 4)
    upsel_def6 = emit_default(data, upsel, core_if, 6)

    # Allocate unique /31 + /127 per access<->policy
    p2p_pool4 = data["site"]["compilerIR"]["addressPools"]["p2p"]["ipv4"]
    p2p_pool6 = data["site"]["compilerIR"]["addressPools"]["p2p"]["ipv6"]
    used_p2p4, used_p2p6 = _gather_used_p2p_addrs(data)

    p2p_links = alloc_p2p_links(
        p2p_pool4,
        p2p_pool6,
        count=len(tenant_domains),
        used_addr4=used_p2p4,
        used_addr6=used_p2p6,
    )

    nodes: Dict[str, Any] = {}
    links: List[Dict[str, Any]] = []

    # ----------------------
    # ACCESS + CLIENTS
    # ----------------------
    for idx, tenant in enumerate(tenant_domains):
        tenant_name = tenant["name"]
        tenant_v4 = tenant["ipv4"]
        tenant_v6 = tenant["ipv6"]

        access_name = f"{access_base}-{tenant_name}"
        client_name = f"client-{tenant_name}"

        link_addrs = p2p_links[idx]

        # Access = first IP in /31,/127
        access_p2p_v4 = str(link_addrs.a4)
        access_p2p_v6 = str(link_addrs.a6)

        # Policy = second IP
        policy_p2p_ip4 = str(link_addrs.b4.ip)
        policy_p2p_ip6 = str(link_addrs.b6.ip)

        gw_v4 = tenant_gateway_v4(tenant_v4)
        gw_v6 = tenant_gateway_v6(tenant_v6)
        host_v4 = tenant_host_ip_v4(tenant_v4)
        host_v6 = tenant_host_ip_v6(tenant_v6)

        nodes[access_name] = {
            "exec": _base_exec()
            + [
                "ip link set eth1 up",
                f"ip addr replace {access_p2p_v4} dev eth1",
                f"ip -6 addr replace {access_p2p_v6} dev eth1",
                "ip link set eth2 up",
                f"ip addr replace {gw_v4}/24 dev eth2",
                f"ip -6 addr replace {gw_v6}/64 dev eth2",
                f"ip route replace default via {policy_p2p_ip4}",
                f"ip -6 route replace default via {policy_p2p_ip6}",
            ],
        }

        nodes[client_name] = {
            "exec": [
                "ip link set eth1 up",
                f"ip addr replace {host_v4} dev eth1",
                f"ip -6 addr replace {host_v6} dev eth1",
                f"ip route replace default via {gw_v4}",
                f"ip -6 route replace default via {gw_v6}",
            ]
        }

        links.append({"endpoints": [f"{access_name}:eth2", f"{client_name}:eth1"]})

    # ----------------------
    # POLICY
    # ----------------------
    policy_exec: List[str] = _base_exec()

    # Access-facing interfaces
    for idx, tenant in enumerate(tenant_domains):
        tenant_name = tenant["name"]
        eth = idx + 1
        link_addrs = p2p_links[idx]

        policy_exec += [
            f"ip link set eth{eth} up",
            f"ip addr replace {link_addrs.b4} dev eth{eth}",
            f"ip -6 addr replace {link_addrs.b6} dev eth{eth}",
        ]

        access_name = f"{access_base}-{tenant_name}"
        links.append({"endpoints": [f"{access_name}:eth1", f"{policy}:eth{eth}"]})

    # Upstream interface
    up_eth = len(tenant_domains) + 1
    policy_up_addr4 = data["site"]["links"][policy_if_up]["endpoints"][policy]["addr4"]
    policy_up_addr6 = data["site"]["links"][policy_if_up]["endpoints"][policy]["addr6"]

    policy_exec += [
        f"ip link set eth{up_eth} up",
        f"ip addr replace {policy_up_addr4} dev eth{up_eth}",
        f"ip -6 addr replace {policy_up_addr6} dev eth{up_eth}",
    ]

    # Tenant routes -> correct access peer
    for idx, tenant in enumerate(tenant_domains):
        tenant_v4 = tenant["ipv4"]
        tenant_v6 = tenant["ipv6"]
        link_addrs = p2p_links[idx]

        policy_exec += [
            f"ip route replace {tenant_v4} via {link_addrs.a4.ip}",
            f"ip -6 route replace {tenant_v6} via {link_addrs.a6.ip}",
        ]

    policy_exec += [
        f"ip route replace default via {policy_def4}",
        f"ip -6 route replace default via {policy_def6}",
    ]

    nodes[policy] = {"exec": policy_exec}

    # ----------------------
    # UPSTREAM SELECTOR
    # ----------------------
    nodes[upsel] = {
        "exec": _base_exec()
        + [
            "ip link set eth1 up",
            "ip link set eth2 up",
            f"ip addr replace {data['site']['links'][core_if]['endpoints'][upsel]['addr4']} dev eth1",
            f"ip -6 addr replace {data['site']['links'][core_if]['endpoints'][upsel]['addr6']} dev eth1",
            f"ip addr replace {data['site']['links'][upsel_if]['endpoints'][upsel]['addr4']} dev eth2",
            f"ip -6 addr replace {data['site']['links'][upsel_if]['endpoints'][upsel]['addr6']} dev eth2",
            # 🔥 FIX: ensure return path to tenants via policy
        ]
        + [f"ip route replace {v4} via {policy_up_addr4.split('/')[0]}" for v4 in tenants_v4]
        + [f"ip -6 route replace {v6} via {policy_up_addr6.split('/')[0]}" for v6 in tenants_v6]
        + [
            f"ip route replace default via {upsel_def4}",
            f"ip -6 route replace default via {upsel_def6}",
        ],
    }

    # ----------------------
    # CORE
    # ----------------------
    nodes[core] = {
        "exec": _base_exec()
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

    # ----------------------
    # ISP
    # ----------------------
    nodes["isp"] = {
        "exec": _base_exec()
        + [
            "ip link set eth1 up",
            f"ip addr replace {ISP_ISP_V4} dev eth1",
            f"ip -6 addr replace {ISP_ISP_V6} dev eth1",
        ]
        + [f"ip route replace {v4} via 203.0.113.1" for v4 in tenants_v4]
        + [f"ip -6 route replace {v6} via 2001:db8:ffff::1" for v6 in tenants_v6],
    }

    links += [
        {"endpoints": [f"{policy}:eth{up_eth}", f"{upsel}:eth2"]},
        {"endpoints": [f"{core}:eth1", f"{upsel}:eth1"]},
        {"endpoints": [f"{core}:eth2", "isp:eth1"]},
    ]

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
            "links": links,
        },
    }

    with topo_path.open("w") as f:
        yaml.dump(topology, f, sort_keys=False)


if __name__ == "__main__":
    main()
