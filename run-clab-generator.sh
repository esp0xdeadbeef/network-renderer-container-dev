#!/usr/bin/env bash
set -euo pipefail
#nix run .#generate-clab-config ../network-compiler/examples/single-wan/inputs.nix
nix run .#generate-clab-config ../network-compiler/examples/multi-wan/inputs.nix
