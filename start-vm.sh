rm ./nixos.qcow2
nix run --extra-experimental-features 'nix-command flakes' nixpkgs#nixos-shell vm.nix
