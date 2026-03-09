from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple


ZONES = ("admin", "client", "mgmt", "wan")
TENANT_ZONES = ("admin", "client", "mgmt")




def _zone_from_iface(name: str) -> str | None:
    n = str(name or "").lower()

    if "admin" in n:
        return "admin"
    if "client" in n:
        return "client"
    if "mgmt" in n:
        return "mgmt"

    return None


def _zone_from_member_name(name: str) -> str | None:
    n = str(name or "").strip().lower()

    if n in {"admin", "tenant-admin"}:
        return "admin"
    if n in {"client", "tenant-client"}:
        return "client"
    if n in {"mgmt", "tenant-mgmt"}:
        return "mgmt"
    if n in {"wan", "external", "internet", "upstream"}:
        return "wan"

    return _zone_from_iface(n)


def _build_zone_map(node_data: Dict[str, Any]) -> Dict[str, str]:
    parsed = node_data.get("_s88_links")
    if not isinstance(parsed, dict):
        raise RuntimeError("missing _s88_links for policy firewall")

    links = parsed.get("links")
    if not isinstance(links, dict):
        raise RuntimeError("missing _s88_links.links for policy firewall")

    zones: Dict[str, str] = {}

    accesses = links.get("accesses")
    if not isinstance(accesses, list):
        raise RuntimeError("missing _s88_links.links.accesses for policy firewall")

    for link in accesses:
        if not isinstance(link, dict):
            continue

        iface = link.get("ifname")
        eth = link.get("eth")

        if iface is None or eth is None:
            continue

        zone = _zone_from_iface(str(iface))
        if zone is None:
            continue

        zones[zone] = f"eth{eth}"

    wan_candidates: List[int] = []

    upstream = links.get("upstream_selector")
    if isinstance(upstream, dict):
        eth = upstream.get("eth")
        if isinstance(eth, int):
            wan_candidates.append(eth)

    for key, value in links.items():
        if key == "accesses":
            continue

        if isinstance(value, dict):
            eth = value.get("eth")
            if isinstance(eth, int):
                wan_candidates.append(eth)

        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    eth = entry.get("eth")
                    if isinstance(eth, int):
                        wan_candidates.append(eth)

    access_eth = {
        int(zones[z].replace("eth", ""))
        for z in zones
        if z in TENANT_ZONES
    }

    filtered = [e for e in wan_candidates if e not in access_eth]

    if not filtered:
        raise RuntimeError("unable to determine WAN interface")

    wan_eth = min(filtered)

    zones["wan"] = f"eth{wan_eth}"

    missing = [zone for zone in ZONES if zone not in zones]
    if missing:
        raise RuntimeError(f"missing required firewall zones: {', '.join(missing)}")

    return zones


def _iter_site_dicts(enterprise: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for enterprise_obj in enterprise.values():
        if not isinstance(enterprise_obj, dict):
            continue
        site_root = enterprise_obj.get("site")
        if not isinstance(site_root, dict):
            continue
        for site_obj in site_root.values():
            if isinstance(site_obj, dict):
                yield site_obj


def _load_site_context(node_data: Dict[str, Any]) -> Dict[str, Any]:
    enterprise = node_data.get("enterprise")
    if not isinstance(enterprise, dict):
        raise RuntimeError("missing node_data['enterprise']")

    for site_obj in _iter_site_dicts(enterprise):
        return site_obj

    raise RuntimeError("missing site context")


def _load_contract(node_data: Dict[str, Any]) -> Dict[str, Any]:
    site_obj = _load_site_context(node_data)
    contract = site_obj.get("communicationContract")
    if not isinstance(contract, dict):
        raise RuntimeError("missing communicationContract")
    return contract


def _load_ownership(node_data: Dict[str, Any]) -> Dict[str, Any]:
    site_obj = _load_site_context(node_data)
    ownership = site_obj.get("ownership", {})
    if not isinstance(ownership, dict):
        raise RuntimeError("ownership must be an object")
    return ownership


def _load_provider_zone_map(node_data: Dict[str, Any]) -> Dict[str, str]:
    direct = node_data.get("provider_zone_map")
    if isinstance(direct, dict):
        return {
            str(k): str(v)
            for k, v in direct.items()
            if isinstance(k, str) and isinstance(v, str)
        }

    site_obj = _load_site_context(node_data)
    from_site = site_obj.get("providerZoneMap", {})
    if not isinstance(from_site, dict):
        return {}

    return {
        str(k): str(v)
        for k, v in from_site.items()
        if isinstance(k, str) and isinstance(v, str)
    }


def _traffic_map(contract: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    result: Dict[str, List[Dict[str, Any]]] = {}

    traffic_types = contract.get("trafficTypes", [])
    if not isinstance(traffic_types, list):
        return result

    for item in traffic_types:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        match = item.get("match", [])
        if isinstance(name, str) and isinstance(match, list):
            result[name] = [m for m in match if isinstance(m, dict)]

    return result


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

    if kind == "tenant-set":
        members = obj.get("members", [])
        if isinstance(members, list):
            return [str(m) for m in members if isinstance(m, str)]
        return []

    if kind in {"tenant", "external", "zone", "service"}:
        name = obj.get("name")
        if isinstance(name, str):
            return [name]
        return []

    if "members" in obj and isinstance(obj["members"], list):
        return [str(m) for m in obj["members"] if isinstance(m, str)]

    if "name" in obj and isinstance(obj["name"], str):
        return [obj["name"]]

    return []


def _endpoint_tenant_map(ownership: Dict[str, Any]) -> Dict[str, str]:
    result: Dict[str, str] = {}

    endpoints = ownership.get("endpoints", [])
    if not isinstance(endpoints, list):
        return result

    for endpoint in endpoints:
        if not isinstance(endpoint, dict):
            continue

        name = endpoint.get("name")
        tenant = endpoint.get("tenant")

        if isinstance(name, str) and isinstance(tenant, str):
            result[name] = tenant

    return result


def _service_zone_map(contract: Dict[str, Any], ownership: Dict[str, Any], node_data: Dict[str, Any]) -> Dict[str, str]:
    resolved = _load_provider_zone_map(node_data)
    if resolved:
        return resolved

    result: Dict[str, str] = {}
    endpoint_tenants = _endpoint_tenant_map(ownership)

    services = contract.get("services", [])
    if not isinstance(services, list):
        return result

    for service in services:
        if not isinstance(service, dict):
            continue

        name = service.get("name")
        providers = service.get("providers", [])

        if not isinstance(name, str):
            continue

        resolved_zone: str | None = None

        if isinstance(providers, list):
            for provider in providers:
                if not isinstance(provider, str):
                    continue

                tenant = endpoint_tenants.get(provider)
                if tenant:
                    zone = _zone_from_member_name(tenant)
                else:
                    zone = _zone_from_member_name(provider)

                if zone:
                    resolved_zone = zone
                    break

        if resolved_zone:
            result[name] = resolved_zone

    return result


def _relation_matches(contract: Dict[str, Any], relation: Dict[str, Any]) -> List[Dict[str, Any]]:
    match = relation.get("match", [])
    if isinstance(match, list) and match:
        return [m for m in match if isinstance(m, dict)]

    traffic_type = relation.get("trafficType")
    if not isinstance(traffic_type, str):
        return []

    return _traffic_map(contract).get(traffic_type, [])


def _relation_endpoints(relation: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    src_obj = relation.get("from", relation.get("source"))
    dst_obj = relation.get("to", relation.get("destination"))
    return _members(src_obj), _members(dst_obj)


def _relation_action(relation: Dict[str, Any]) -> str:
    action = str(relation.get("action", "allow")).lower()
    if action in {"allow", "accept"}:
        return "accept"
    if action in {"deny", "drop"}:
        return "drop"
    raise RuntimeError(f"unsupported action {action}")


def _relation_priority(relation: Dict[str, Any], index: int) -> Tuple[int, int]:
    priority = relation.get("priority")
    if isinstance(priority, int):
        return priority, index
    return 1_000_000, index


def _proto(match: Dict[str, Any]) -> str | None:
    proto = match.get("proto")
    if proto is None:
        return None
    proto = str(proto).lower()
    if proto == "any":
        return None
    return proto


def _dports(match: Dict[str, Any]) -> List[int]:
    value = (
        match.get("dports")
        or match.get("destinationPorts")
        or match.get("ports")
        or match.get("dport")
        or match.get("port")
    )

    if value is None:
        return []

    items = value if isinstance(value, list) else [value]
    result: List[int] = []

    for i in items:
        if isinstance(i, int):
            result.append(i)
        elif isinstance(i, str) and i.isdigit():
            result.append(int(i))
        else:
            raise RuntimeError(f"invalid port {i}")

    return result


def _zones_for_member(
    member: str,
    zones: Dict[str, str],
    service_zones: Dict[str, str],
) -> List[str]:
    raw = str(member or "").strip().lower()

    if raw == "any":
        return list(zones.keys())

    if raw in {"tenants", "internal"}:
        return [z for z in TENANT_ZONES if z in zones]

    zone = service_zones.get(member) or _zone_from_member_name(member)

    if zone is None:
        raise RuntimeError(f"unable to determine zone for member {member}")

    if zone not in zones:
        raise RuntimeError(f"zone {zone} missing for {member}")

    return [zone]


def _rule_for_match(src_if: str, dst_if: str, match: Dict[str, Any], action: str) -> str:
    proto = _proto(match)
    dports = _dports(match)

    rule = f'nft add rule inet fw forward iifname "{src_if}" oifname "{dst_if}"'

    if proto == "icmp":
        rule += " meta l4proto icmp"
    elif proto:
        rule += f" {proto}"

    if dports:
        if len(dports) == 1:
            rule += f" dport {dports[0]}"
        else:
            ports = ", ".join(str(p) for p in dports)
            rule += f" dport {{ {ports} }}"

    rule += f" {action}"
    return rule


def render(role: str, node_name: str, node_data: Dict[str, Any]) -> List[str]:
    if role != "policy":
        return []


    zones = _build_zone_map(node_data)
    contract = _load_contract(node_data)
    ownership = _load_ownership(node_data)
    service_zones = _service_zone_map(contract, ownership, node_data)

    relations = contract.get("relations")
    if not isinstance(relations, list):
        legacy = contract.get("allowedRelations")
        if isinstance(legacy, list):
            relations = legacy
        else:
            raise RuntimeError("communicationContract.relations must be array")

    cmds: List[str] = [
        "echo '[FW] policy firewall starting'",
        "nft add table inet fw",
        "nft 'add chain inet fw forward { type filter hook forward priority 0 ; policy drop ; }'",
        "nft add rule inet fw forward ct state established,related accept",
        "nft add rule inet fw forward ct state invalid drop",
        'nft add rule inet fw forward iifname "eth0" drop',
        'nft add rule inet fw forward oifname "eth0" drop',
    ]

    emitted_rules: set[str] = set()

    ordered_relations = sorted(
        [r for r in relations if isinstance(r, dict)],
        key=lambda item: _relation_priority(item, relations.index(item)),
    )

    for relation in ordered_relations:
        src_members, dst_members = _relation_endpoints(relation)
        matches = _relation_matches(contract, relation)
        action = _relation_action(relation)

        for s in src_members:
            src_zones = _zones_for_member(s, zones, service_zones)

            for d in dst_members:
                dst_zones = _zones_for_member(d, zones, service_zones)

                for src_zone in src_zones:
                    src_if = zones[src_zone]

                    for dst_zone in dst_zones:
                        if src_zone == dst_zone:
                            continue

                        dst_if = zones[dst_zone]

                        for m in matches:
                            rule = _rule_for_match(src_if, dst_if, m, action)
                            if rule in emitted_rules:
                                continue
                            emitted_rules.add(rule)
                            cmds.append(rule)

    cmds.append("echo '[FW] resulting ruleset:'")
    cmds.append("nft list table inet fw")

    return cmds
