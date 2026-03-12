# ./run-clab-generator.sh
#!/usr/bin/env bash
set -euo pipefail

#nix flake update --flake path:.

find ../network-compiler/examples -name inputs.nix -type f -exec sh -c '
  echo "[*] Running for $1"
  nix run .#generate-clab-config "$1"
' sh {} \;
