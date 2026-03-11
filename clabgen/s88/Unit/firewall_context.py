from __future__ import annotations

from typing import Any, Dict, List

from clabgen.models import SiteModel, NodeModel


def _members(obj: Any) -> List[str]:
    if isinstance(obj, str):
        return [obj]

    if isinstance(obj, list):
        result: List[str] = []
        for item in obj:
            result.extend(_members(item))
        return result

    if not isinstance(obj, dict):
        return []

    kind = obj.get("kind")

    if kind in {"tenant", "tenant-set"}:
        members = obj.get("members")
        if isinstance(members, list):
            return [str(m) for m in members if isinstance(m, str)]
        name = obj.get("name")
        if isinstance(name, str):
            return [name]

    if kind in {"external", "service"}:
        name = obj.get("name")
        if isinstance(name, str):
            return [name]

    return []


def _relation_objects(contract: Dict[str, Any]) -> List[Dict[str, Any]]:
    relations = contract.get("allowedRelations") or contract.get("relations")
    if not isinstance(relations, list):
        raise RuntimeError("communicationContract.allowedRelations must be array")
    return [r for r in relations if isinstance(r, dict)]


def _contract_tenant_names(contract: Dict[str, Any]) -> List[str]:
    result: set[str] = set()

    for relation in _relation_objects(contract):
        for side in ("from", "to"):
            endpoint = relation.get(side)
            if not isinstance(endpoint, dict):
                continue
            if endpoint.get("kind") in {"tenant", "tenant-set"}:
                result.update(_members(endpoint))

    return sorted(result)


def _contract_external_names(contract: Dict[str, Any]) -> List[str]:
    result: set[str] = set()

    for relation in _relation_objects(contract):
        for side in ("from", "to"):
            endpoint = relation.get(side)
            if not isinstance(endpoint, dict):
                continue
            if endpoint.get("kind") == "external":
                result.update(_members(endpoint))

    return sorted(result)


def _policy_peer_map(
    site: SiteModel,
    policy_node_name: str,
    eth_map: Dict[str, int],
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    for _, link in sorted(site.links.items(), key=lambda item: item[0]):
        endpoints = link.endpoints
        local = endpoints.get(policy_node_name)
        if not isinstance(local, dict):
            continue

        local_ifname = local.get("interface")
        if not isinstance(local_ifname, str):
            raise RuntimeError("policy endpoint missing interface")

        eth = eth_map.get(local_ifname)
        if eth is None:
            raise RuntimeError(f"missing eth mapping for {local_ifname}")

        peers = [n for n in endpoints.keys() if n != policy_node_name]
        if len(peers) != 1:
            raise RuntimeError("policy link must have exactly one peer")

        results.append(
            {
                "eth": eth,
                "peer_name": peers[0],
                "link_name": link.name,
                "ifname": local_ifname,
            }
        )

    return results


def _access_node_tenant_zone(access_node_name: str, site: SiteModel) -> str:
    access_node = site.nodes.get(access_node_name)
    if access_node is None:
        raise RuntimeError(f"missing topology node {access_node_name!r}")

    if access_node.role != "access":
        raise RuntimeError(
            f"policy access link peer {access_node_name!r} is not an access node"
        )

    tenant_zones: set[str] = set()

    for ifname, iface in access_node.interfaces.items():
        if iface.kind != "tenant":
            continue

        tenant_name: str | None = None

        if isinstance(ifname, str) and ifname.startswith("tenant-"):
            tenant_name = ifname.split("tenant-", 1)[1]

        if tenant_name:
            tenant_zones.add(tenant_name)

    if not tenant_zones:
        raise RuntimeError(
            f"tenant zone cannot be resolved for access node {access_node_name!r}. "
            f"Interfaces seen: {list(access_node.interfaces.keys())}"
        )

    if len(tenant_zones) != 1:
        raise RuntimeError(
            f"multiple tenant zones on access node {access_node_name!r}: {sorted(tenant_zones)}"
        )

    return next(iter(tenant_zones))


def _build_policy_zone_interfaces(
    site: SiteModel,
    policy_node_name: str,
    eth_map: Dict[str, int],
    required_tenants: set[str],
    required_externals: set[str],
) -> Dict[str, str]:
    zones: Dict[str, str] = {}
    wan_if: str | None = None

    for peer in _policy_peer_map(site, policy_node_name, eth_map):
        peer_name = peer["peer_name"]
        peer_node = site.nodes.get(peer_name)
        if peer_node is None:
            raise RuntimeError(f"missing topology node {peer_name!r}")

        iface = f"eth{peer['eth']}"

        if peer_node.role == "access":
            tenant_zone = _access_node_tenant_zone(peer_name, site)

            if tenant_zone in zones and zones[tenant_zone] != iface:
                raise RuntimeError(
                    f"multiple policy interfaces resolve to tenant zone {tenant_zone}"
                )

            zones[tenant_zone] = iface
            continue

        if peer_node.role == "upstream-selector":
            if wan_if is not None and wan_if != iface:
                raise RuntimeError("multiple WAN interfaces detected")

            wan_if = iface
            continue

    if wan_if is None:
        raise RuntimeError("wan cannot be resolved from topology")

    zones["wan"] = wan_if

    for tenant in required_tenants:
        if tenant not in zones:
            raise RuntimeError(
                f"tenant zone {tenant} cannot be mapped to a policy interface"
            )

    for external in required_externals:
        if external != "wan":
            raise RuntimeError(
                f"external zone {external} cannot be mapped from topology"
            )

    return zones


def _build_policy_rules(
    contract: Dict[str, Any],
    zone_interfaces: Dict[str, str],
) -> List[Dict[str, Any]]:
    rules: List[Dict[str, Any]] = []

    for relation in _relation_objects(contract):
        src_members = _members(relation.get("from"))
        dst_obj = relation.get("to")

        if dst_obj == "any":
            dst_members = list(zone_interfaces.keys())
        else:
            dst_members = _members(dst_obj)

        matches = relation.get("match") or []
        action = "accept" if relation.get("action") == "allow" else "drop"

        if not isinstance(matches, list):
            matches = []

        for src_zone in src_members:
            for dst_zone in dst_members:
                if src_zone == dst_zone:
                    continue
                if src_zone not in zone_interfaces:
                    continue
                if dst_zone not in zone_interfaces:
                    continue

                rules.append(
                    {
                        "src_zone": src_zone,
                        "dst_zone": dst_zone,
                        "action": action,
                        "matches": [m for m in matches if isinstance(m, dict)],
                    }
                )

    return rules


def build_policy_firewall_cm_input(
    site: SiteModel,
    policy_node_name: str,
    eth_map: Dict[str, int],
) -> Dict[str, Any]:
    contract = dict(site.raw_policy or {})
    required_tenants = set(_contract_tenant_names(contract))
    required_externals = set(_contract_external_names(contract))

    zone_interfaces = _build_policy_zone_interfaces(
        site=site,
        policy_node_name=policy_node_name,
        eth_map=eth_map,
        required_tenants=required_tenants,
        required_externals=required_externals,
    )

    rules = _build_policy_rules(contract, zone_interfaces)

    return {
        "zone_interfaces": zone_interfaces,
        "rules": rules,
    }


def build_node_firewall_context(
    site: SiteModel,
    node_name: str,
    node: NodeModel,
    eth_map: Dict[str, int],
) -> Dict[str, Any]:
    if node.role == "policy":
        return {
            "firewall": build_policy_firewall_cm_input(site, node_name, eth_map),
        }

    return {}
