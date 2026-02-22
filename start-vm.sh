rm ./nixos.qcow2
export QEMU_NET_OPTS="hostfwd=tcp::2222-:22"
echo "ssh -p2222 root@localhost # to connect to the vm."
nix run --extra-experimental-features 'nix-command flakes' nixpkgs#nixos-shell vm.nix
