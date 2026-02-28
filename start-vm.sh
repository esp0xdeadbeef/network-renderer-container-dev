# ./start-vm.sh
#!/usr/bin/env bash
set -euo pipefail

touch ./nixos.qcow2
rm -f ./nixos.qcow2

export QEMU_NET_OPTS="hostfwd=tcp::2222-:22"
echo "ssh -o 'StrictHostKeyChecking no' -p2222 root@localhost # to connect to the vm."

FLAKE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[*] Generating bridges-generated.nix ..."
python3 "${FLAKE_DIR}/generate-vm-bridges.py" "${FLAKE_DIR}/output-network-solver.json" "${FLAKE_DIR}/bridges-generated.nix"

echo "[*] Starting VM via nixos-shell (preserving custom options)..."
nix run --extra-experimental-features 'nix-command flakes' nixpkgs#nixos-shell -- "${FLAKE_DIR}/vm.nix"
