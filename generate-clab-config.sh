#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

INPUT_NIX="${1:-$SCRIPT_DIR/../network-compiler/examples/single-wan/inputs.nix}"
OUTPUT_JSON="${2:-$SCRIPT_DIR/output-network-solver.json}"
TOPO_OUT="${3:-$SCRIPT_DIR/fabric.clab.yml}"

(cd ~/github/network-solver; nix run .#compile-and-solve -- ../network-compiler/examples/single-wan/inputs.nix) > ./output-network-solver.json
# 3) Run generator
nix run "path:$SCRIPT_DIR#generate-clab-config" -- \
  "$OUTPUT_JSON" "$TOPO_OUT"
