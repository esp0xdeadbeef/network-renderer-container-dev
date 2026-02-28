# FILE: ./clabgen/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class InterfaceModel:
    name: str
    addr4: Optional[str] = None
    addr6: Optional[str] = None
    ll6: Optional[str] = None
    routes4: List[Dict] = field(default_factory=list)
    routes6: List[Dict] = field(default_factory=list)


@dataclass
class NodeModel:
    name: str
    role: str
    routing_domain: str
    interfaces: Dict[str, InterfaceModel]
    containers: List[str] = field(default_factory=list)


@dataclass
class LinkModel:
    name: str
    kind: str
    endpoints: Dict[str, str]  # unit -> linkKey


@dataclass
class SiteModel:
    enterprise: str
    site: str
    nodes: Dict[str, NodeModel]
    links: Dict[str, LinkModel]
    single_access: str
