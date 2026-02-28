import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional


def fail(msg: str, context: Any = None) -> None:
    print(f"[solver.py] ERROR: {msg}", file=sys.stderr)
    if context is not None:
        try:
            dumped = json.dumps(context, indent=2, sort_keys=True)
        except Exception:
            dumped = str(context)
        print("[solver.py] CONTEXT:", file=sys.stderr)
        print(dumped, file=sys.stderr)
    sys.exit(1)


def load_solver(path: Path) -> Dict[str, Any]:
    if not path.exists():
        fail(f"Solver JSON not found: {path}")
    with path.open() as f:
        return json.load(f)


def _fmt_path(path: List[str]) -> str:
    return ".".join(path) if path else "<root>"


def get_required(d: Dict[str, Any], path: List[str], desc: str, *, context: Any = None):
    cur: Any = d
    walked: List[str] = []
    for p in path:
        walked.append(p)
        if not isinstance(cur, dict) or p not in cur:
            fail(
                f"Missing required solver field: {desc} at {_fmt_path(walked)}",
                context=context if context is not None else d,
            )
        cur = cur[p]
    return cur


def _get_meta_schema_version(data: Dict[str, Any]) -> int:
    meta = data.get("meta")
    if not isinstance(meta, dict):
        fail("Missing required solver field: meta", context=data)

    solver_meta = meta.get("solver")
    if isinstance(solver_meta, dict):
        v = solver_meta.get("schemaVersion")
        if isinstance(v, int):
            return v

    fail("Invalid or missing meta.solver.schemaVersion (expected integer)", context=meta)


def extract_enterprise_sites(data: Dict[str, Any]) -> List[Tuple[str, str, Dict[str, Any]]]:
    schema_version = _get_meta_schema_version(data)

    if schema_version != 2:
        fail(
            f"Unsupported solver schemaVersion={schema_version}. Supported: 2 (enterprise-aware only).",
            context=data.get("meta"),
        )

    sites = data.get("sites")
    if not isinstance(sites, dict):
        fail("Missing required solver field: sites", context=data)

    results: List[Tuple[str, str, Dict[str, Any]]] = []

    for ent_name, ent_obj in sites.items():
        if not isinstance(ent_obj, dict):
            fail(f"Invalid enterprise object at sites.{ent_name}", context=ent_obj)

        for site_name, site_obj in ent_obj.items():
            if not isinstance(site_obj, dict):
                fail(
                    f"Invalid site object at sites.{ent_name}.{site_name}",
                    context=site_obj,
                )
            results.append((ent_name, site_name, site_obj))

    if not results:
        fail("No sites found under sites.<enterprise>.<site>", context=sites)

    return results


def _derive_routing_assumptions_from_traversal(site: Dict[str, Any], *, context: Any) -> Dict[str, Any]:
    rm = site.get("_routingMaps")
    if not isinstance(rm, dict):
        fail("Missing required solver field: site._routingMaps", context=context)

    trav = rm.get("traversal")
    if not isinstance(trav, dict):
        fail("Missing required solver field: site._routingMaps.traversal", context=context)

    core = trav.get("coreUnitHint")
    access = trav.get("accessUnitHint")
    inferred = trav.get("inferred", {})
    if not isinstance(inferred, dict):
        inferred = {}

    if not isinstance(core, str) or not core:
        fail("Missing required routing assumption: derived core (site._routingMaps.traversal.coreUnitHint)", context=context)
    if not isinstance(access, str) or not access:
        fail("Missing required routing assumption: derived singleAccess (site._routingMaps.traversal.accessUnitHint)", context=context)

    policy: Optional[str] = None
    upstream: Optional[str] = None
    for n, role in inferred.items():
        if role == "policy" and policy is None:
            policy = n
        if role == "upstream-selector" and upstream is None:
            upstream = n

    if not isinstance(policy, str) or not policy:
        fail("Missing required routing assumption: derived policy (site._routingMaps.traversal.inferred[*] == 'policy')", context=context)

    out: Dict[str, Any] = {
        "core": core,
        "policy": policy,
        "singleAccess": access,
        "upstreamSelector": upstream,  # may be None in some modes
    }
    return out


def validate_routing_assumptions(site: Dict[str, Any], *, context: Any = None) -> Dict[str, Any]:
    ctx = context if context is not None else site

    rm = site.get("_routingMaps")
    if isinstance(rm, dict) and isinstance(rm.get("assumptions"), dict):
        assumptions = rm["assumptions"]
        for k in ("core", "policy", "singleAccess"):
            if k not in assumptions or not isinstance(assumptions[k], str) or not assumptions[k]:
                fail(f"Missing required routing assumption: site._routingMaps.assumptions.{k}", context=ctx)

        if "upstreamSelector" in assumptions and assumptions["upstreamSelector"] is not None:
            if not isinstance(assumptions["upstreamSelector"], str) or not assumptions["upstreamSelector"]:
                fail("Invalid routing assumption: site._routingMaps.assumptions.upstreamSelector", context=ctx)

        return assumptions

    # Compatibility: solver may omit _routingMaps.assumptions; derive from traversal hints.
    return _derive_routing_assumptions_from_traversal(site, context=ctx)


def validate_site_invariants(site: Dict[str, Any], *, context: Any = None) -> None:
    ctx = context if context is not None else site

    validate_routing_assumptions(site, context=ctx)

    links = site.get("links")
    if not isinstance(links, dict):
        fail("Missing required solver field: site.links (expected object)", context=ctx)

    nodes = site.get("nodes")
    if not isinstance(nodes, dict):
        fail("Missing required solver field: site.nodes (expected object)", context=ctx)

    for link_name, link in links.items():
        if not isinstance(link, dict):
            fail(f"Invalid link object at site.links.{link_name}", context=ctx)
        eps = link.get("endpoints")
        if not isinstance(eps, dict) or len(eps) < 1:
            fail(f"Invalid endpoints at site.links.{link_name}.endpoints", context=ctx)
        for n, ep in eps.items():
            if n not in nodes:
                fail(f"Link references unknown node: site.links.{link_name}.endpoints.{n}", context=ctx)
            if not isinstance(ep, dict):
                fail(f"Invalid endpoint object at site.links.{link_name}.endpoints.{n}", context=ctx)
            for addrk in ("addr4", "addr6"):
                if addrk in ep and ep[addrk] is not None and not isinstance(ep[addrk], str):
                    fail(
                        f"Invalid endpoint address type at site.links.{link_name}.endpoints.{n}.{addrk}",
                        context=ctx,
                    )

    for node_name, node in nodes.items():
        if not isinstance(node, dict):
            fail(f"Invalid node object at site.nodes.{node_name}", context=ctx)
        ifaces = node.get("interfaces", {}) or {}
        if not isinstance(ifaces, dict):
            fail(f"Invalid interfaces object at site.nodes.{node_name}.interfaces", context=ctx)
        for if_name, iface in ifaces.items():
            if if_name not in links:
                fail(f"Interface references unknown link: site.nodes.{node_name}.interfaces.{if_name}", context=ctx)
            if not isinstance(iface, dict):
                fail(f"Invalid interface object at site.nodes.{node_name}.interfaces.{if_name}", context=ctx)
