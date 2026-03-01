# ./clabgen/solver.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple


def load_solver(path: Path) -> Dict[str, Any]:
    with path.open() as f:
        return json.load(f)


def extract_enterprise_sites(data: Dict[str, Any]) -> Iterable[Tuple[str, str, Dict[str, Any]]]:
    sites = data.get("sites", {})
    for enterprise, site_map in sites.items():
        for site_name, site_obj in site_map.items():
            yield enterprise, site_name, site_obj


def validate_site_invariants(site: Dict[str, Any], context: Dict[str, str] | None = None) -> None:
    if "nodes" not in site or "links" not in site:
        raise ValueError(
            f"Invalid site schema for {context or {}}: missing 'nodes' or 'links'"
        )


def validate_routing_assumptions(site: Dict[str, Any]) -> Dict[str, Any]:
    # Deterministic default: no synthetic assumptions.
    return {
        "singleAccess": ""
    }
