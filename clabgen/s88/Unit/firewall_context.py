from __future__ import annotations

from typing import Any, Dict, List
import json
import ipaddress

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
        raise RuntimeError(
            "communicationContract.allowedRelations must be array\n"
            + json.dumps(contract, indent=2, default=str)
        )
    return [r for r in relations if isinstance(r, dict)]


def _contract_tenant_names(contract: Dict[str, Any]) -> List[str]:
    result: set[str] = set()

    for relation in _relation_objects(contract):
        for side in ("from", "to"):
            endpoint = relation.get(side)
            if isinstance(endpoint, dict) and endpoint.get("kind") in {"tenant", "tenant-set"}:
                result.update(_members(endpoint))

    return sorted(result)


def _contract_external_names(contract: Dict[str, Any]) -> List[str]:
    result: set[str] = set()

    for relation in _relation_objects(contract):
        for side in ("from", "to"):
            endpoint = relation.get(side)
            if isinstance(endpoint, dict) and endpoint.get("kind") == "external":
                result.update(_members(endpoint))

    return sorted(result)


def _policy_peer_map(site: SiteModel, policy_node_name: str, eth_map: Dict[str, int]):
    results = []

    for _, link in sorted(site.links.items(), key=lambda x: x[0]):
        endpoints = link.endpoints
        local = endpoints.get(policy_node_name)

        if not isinstance(local, dict):
            continue

        iface = local.get("interface")
        if iface not in eth_map:
            raise RuntimeError(
                f"missing eth mapping for interface {iface}\n"
                + json.dumps(local, indent=2, default=str)
            )

        peers = [n for n in endpoints if n != policy_node_name]
        if len(peers) != 1:
            raise RuntimeError(
                "policy link must have exactly one peer\n"
                + json.dumps(link.__dict__, indent=2, default=str)
            )

        results.append(
            {
                "eth": eth_map[iface],
                "peer_name": peers[0],
                "link": link.name,
            }
        )

    return results


def _networks_for_iface(iface: Any) -> List[str]:
    result: List[str] = []

    for addr in (getattr(iface, "addr4", None), getattr(iface, "addr6", None)):
        if not isinstance(addr, str) or not addr:
            continue
        try:
            result.append(str(ipaddress.ip_interface(addr).network))
        except ValueError:
            continue

    return result


def _access_node_tenant_zones(node: NodeModel, site: SiteModel) -> List[str]:
    zones: set[str] = set()
    prefix_zone_map = dict(site.tenant_prefix_owners or {})

    for _, iface in node.interfaces.items():
        if getattr(iface, "kind", None) != "tenant":
            continue

        for network in _networks_for_iface(iface):
            zone = prefix_zone_map.get(network)
            if isinstance(zone, str) and zone:
                zones.add(zone)

    if not zones:
        debug = {
            "node": node.name,
            "role": node.role,
            "interfaces": {
                name: getattr(iface, "__dict__", str(iface))
                for name, iface in node.interfaces.items()
            },
            "tenant_prefix_owners": prefix_zone_map,
        }

        raise RuntimeError(
            "tenant zone cannot be resolved for access node\n"
            + json.dumps(debug, indent=2, default=str)
        )

    return sorted(zones)


def _build_policy_zone_interfaces(
    site: SiteModel,
    policy_node_name: str,
    eth_map: Dict[str, int],
    required_tenants: set[str],
    required_externals: set[str],
):
    zones: Dict[str, str] = {}
    external_interfaces: Dict[str, str] = {}

    peer_map = _policy_peer_map(site, policy_node_name, eth_map)

    for peer in peer_map:
        peer_node = site.nodes.get(peer["peer_name"])

        if peer_node is None:
            raise RuntimeError(
                f"peer node missing: {peer['peer_name']}\n"
                + json.dumps(sorted(site.nodes.keys()), indent=2, default=str)
            )

        iface = f"eth{peer['eth']}"

        if peer_node.role == "access":
            for zone in _access_node_tenant_zones(peer_node, site):
                if zone in zones and zones[zone] != iface:
                    raise RuntimeError(
                        "tenant zone resolved to multiple policy interfaces\n"
                        + json.dumps(
                            {
                                "zone": zone,
                                "existing_interface": zones[zone],
                                "new_interface": iface,
                                "peer_node": peer_node.name,
                            },
                            indent=2,
                            default=str,
                        )
                    )
                zones[zone] = iface
            continue

        if peer_node.role == "upstream-selector":
            external_interfaces["wan"] = iface
            for external in sorted(required_externals):
                if external_interfaces.get(external) not in {None, iface}:
                    raise RuntimeError(
                        "external zone resolved to multiple policy interfaces\n"
                        + json.dumps(
                            {
                                "zone": external,
                                "existing_interface": external_interfaces[external],
                                "new_interface": iface,
                                "peer_node": peer_node.name,
                            },
                            indent=2,
                            default=str,
                        )
                    )
                external_interfaces[external] = iface
            continue

        if peer_node.role == "core":
            wan_uplinks: List[str] = []
            for core_iface in peer_node.interfaces.values():
                if getattr(core_iface, "kind", None) != "wan":
                    continue
                uplink = getattr(core_iface, "upstream", None)
                if isinstance(uplink, str) and uplink:
                    wan_uplinks.append(uplink)

            wan_uplinks = sorted(set(wan_uplinks))

            if not wan_uplinks:
                external_interfaces["wan"] = iface
            else:
                for uplink in wan_uplinks:
                    if uplink in external_interfaces and external_interfaces[uplink] != iface:
                        raise RuntimeError(
                            "external zone resolved to multiple policy interfaces\n"
                            + json.dumps(
                                {
                                    "zone": uplink,
                                    "existing_interface": external_interfaces[uplink],
                                    "new_interface": iface,
                                    "peer_node": peer_node.name,
                                },
                                indent=2,
                                default=str,
                            )
                        )
                    external_interfaces[uplink] = iface
            continue

    if not external_interfaces:
        raise RuntimeError(
            "wan cannot be resolved from topology\n"
            + json.dumps(peer_map, indent=2, default=str)
        )

    if "wan" not in external_interfaces:
        if len(external_interfaces) == 1:
            external_interfaces["wan"] = next(iter(external_interfaces.values()))
        elif "wan" in required_externals:
            raise RuntimeError(
                "external zone 'wan' cannot be resolved from topology\n"
                + json.dumps(
                    {
                        "external_interfaces": external_interfaces,
                        "required_externals": sorted(required_externals),
                        "peer_map": peer_map,
                    },
                    indent=2,
                    default=str,
                )
            )

    zones.update(external_interfaces)

    for external in required_externals:
        if external not in zones:
            raise RuntimeError(
                f"external zone {external} cannot be mapped from topology\n"
                + json.dumps(
                    {
                        "zones": zones,
                        "required_externals": sorted(required_externals),
                        "peer_map": peer_map,
                    },
                    indent=2,
                    default=str,
                )
            )

    for tenant in required_tenants:
        if tenant not in zones:
            raise RuntimeError(
                f"tenant zone {tenant} cannot be mapped to policy interface\n"
                + json.dumps(
                    {
                        "zones": zones,
                        "required_tenants": sorted(required_tenants),
                        "policy_node": policy_node_name,
                        "peer_map": peer_map,
                    },
                    indent=2,
                    default=str,
                )
            )

    return zones


def _build_policy_rules(contract: Dict[str, Any], zone_interfaces: Dict[str, str]):
    rules = []

    for relation in _relation_objects(contract):
        src = _members(relation.get("from"))
        dst = relation.get("to")

        if dst == "any":
            dst_members = list(zone_interfaces.keys())
        else:
            dst_members = _members(dst)

        action = "accept" if relation.get("action") == "allow" else "drop"
        matches = relation.get("match") or []

        for s in src:
            for d in dst_members:
                if s == d:
                    continue
                if s not in zone_interfaces or d not in zone_interfaces:
                    continue

                rules.append(
                    {
                        "src_zone": s,
                        "dst_zone": d,
                        "action": action,
                        "matches": matches,
                    }
                )

    return rules


def build_policy_firewall_state(site: SiteModel, policy_node_name: str, eth_map: Dict[str, int]):
    contract = dict(site.raw_policy or {})

    tenants = set(_contract_tenant_names(contract))
    externals = set(_contract_external_names(contract))

    zone_interfaces = _build_policy_zone_interfaces(
        site,
        policy_node_name,
        eth_map,
        tenants,
        externals,
    )

    rules = _build_policy_rules(contract, zone_interfaces)

    return {
        "zone_interfaces": zone_interfaces,
        "rules": rules,
    }


def build_node_firewall_state(
    site: SiteModel,
    node_name: str,
    node: NodeModel,
    eth_map: Dict[str, int],
):
    if node.role == "policy":
        return {
            "policy_firewall_state": build_policy_firewall_state(
                site,
                node_name,
                eth_map,
            )
        }

    return {}
