{
  description = "Containerlab VM host";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
  };

  outputs =
    { self, nixpkgs }:
    let
      system = "x86_64-linux";
    in
    {
      nixosConfigurations.lab = nixpkgs.lib.nixosSystem {
        inherit system;
        modules = [ ./vm.nix ];
      };

      apps.${system}.lab = {
        type = "app";
        program = toString (
          nixpkgs.legacyPackages.${system}.writeShellScript "run-lab" ''
            set -e
            nix build .
            ./result/bin/run-lab-vm
          ''
        );
      };
    };
}
