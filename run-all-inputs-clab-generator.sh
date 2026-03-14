#!/usr/bin/env bash
set -euo pipefail

find ../network-compiler/examples -name inputs.nix -type f | while read -r file; do
  echo "[*] Running for $file"

  if ! nix run .#generate-clab-config "$file"; then
    echo
    echo "[!] Generation failed for: $file"
    echo "[!] Dumping JSON files:"
    echo

    echo "Inputs file:"
    echo "===== $file ====="
    cat $file
    echo 
    

    for j in ./*.json; do
      [ -e "$j" ] || continue
      echo "===== $j ====="
      cat "$j" | jq -c 
      echo
    done

    exit 1
  fi
done
