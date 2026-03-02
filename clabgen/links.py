# ./clabgen/links.py
from __future__ import annotations

from typing import Dict
import hashlib

from .models import SiteModel


def build_eth_index(site: SiteModel) -> Dict[str, Dict[str, int]]:
    eth_index: Dict[str, Dict[str, int]] = {}

    for unit in site.nodes.keys():
        eth_index[unit] = {}

    # Reserve eth0 for containerlab management NIC.
    # Dataplane interfaces start at eth1.
    counters: Dict[str, int] = {u: 1 for u in site.nodes.keys()}

    # deterministic ordering
    for link_name in sorted(site.links.keys()):
        link = site.links[link_name]
        for unit in sorted(link.endpoints.keys()):
            if unit not in eth_index:
                continue
            eth_index[unit][link_name] = counters[unit]
            counters[unit] += 1

    return eth_index


def short_bridge(name: str) -> str:
    # linux bridge name limit is 15 chars
    # enforce deterministic 15-char max: "br-" + 12 hex chars = 15
    h = hashlib.sha1(name.encode()).hexdigest()[:12]
    return f"br-{h}"
