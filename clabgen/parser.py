# ./clabgen/parser.py
from __future__ import annotations

from typing import Dict
from pathlib import Path

from clabgen.solver import (
    load_solver,
    extract_enterprise_sites,
    validate_site_invariants,
    validate_routing_assumptions,
)

from .models import SiteModel, NodeModel, InterfaceModel, LinkModel


def parse_solver(path: str | Path) -> Dict[str, SiteModel]:
    solver_path = Path(path)

    data = load_solver(solver_path)
    sites_raw = extract_enterprise_sites(data)

    result: Dict[str, SiteModel] = {}

    for ent, site_name, site in sites_raw:
        validate_site_invariants(site, context={"enterprise": ent, "site": site_name})
        assumptions = validate_routing_assumptions(site)

        nodes: Dict[str, NodeModel] = {}
        for unit, node_obj in site["nodes"].items():
            interfaces: Dict[str, InterfaceModel] = {}
            for link_key, iface in node_obj.get("interfaces", {}).items():
                interfaces[link_key] = InterfaceModel(
                    name=link_key,
                    addr4=iface.get("addr4"),
                    addr6=iface.get("addr6"),
                    ll6=iface.get("ll6"),
                    routes4=iface.get("routes4", []),
                    routes6=iface.get("routes6", []),
                )

            nodes[unit] = NodeModel(
                name=unit,
                role=node_obj.get("role", ""),
                routing_domain=node_obj.get("routingDomain", ""),
                interfaces=interfaces,
                containers=node_obj.get("containers", []),
            )

        links: Dict[str, LinkModel] = {}
        for lk, lo in site["links"].items():
            links[lk] = LinkModel(
                name=lk,
                kind=lo.get("kind", "lan"),
                endpoints=lo.get("endpoints", {}),
            )

        key = f"{ent}-{site_name}"
        result[key] = SiteModel(
            enterprise=ent,
            site=site_name,
            nodes=nodes,
            links=links,
            single_access=assumptions["singleAccess"],
        )

    return result
