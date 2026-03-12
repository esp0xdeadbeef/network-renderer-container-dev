from __future__ import annotations

from typing import Dict, Any, List

from .policy_firewall import render as render_policy_firewall


def render(input_data: Dict[str, Any]) -> List[str]:
    return render_policy_firewall(input_data)
