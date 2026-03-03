# ./clabgen/fabric_static.py
from __future__ import annotations

FABRIC_YAML = """name: fabric

"""
with open('./fabric.clab.yml.working-up-downstream-static', 'r') as f:
    FABRIC_YAML = f.read()

FABRIC_BRIDGES_NIX = """{ lib, ... }:
{
  bridges = [
    "br-26ec11ee8593"
    "br-749a740b5ae3"
    "br-9b64a30dbc0b"
    "br-c7141be66382"
  ];
}
"""
