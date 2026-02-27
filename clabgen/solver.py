# ./clabgen/solver.py
import sys
import json
from pathlib import Path
from typing import Dict, Any, List


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def load_solver(path: Path) -> Dict[str, Any]:
    if not path.exists():
        fail(f"Solver JSON not found: {path}")
    with path.open() as f:
        return json.load(f)


def get_required(d: Dict[str, Any], path: List[str], desc: str):
    cur = d
    for p in path:
        if p not in cur:
            fail(f"Missing required solver field: {desc}")
        cur = cur[p]
    return cur
