{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";

    network-solver.url = "path:/home/deadbeef/github/network-solver";
    network-compiler.url = "path:/home/deadbeef/github/network-compiler";

    network-solver.inputs.nixpkgs.follows = "nixpkgs";
    network-compiler.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, network-solver, network-compiler }:
  let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};

    pythonEnv = pkgs.python3.withPackages (ps: [
      ps.pyyaml
      ps.pandas
    ]);
  in {

    # ✅ VM restored
    nixosConfigurations.lab = nixpkgs.lib.nixosSystem {
      inherit system;
      modules = [ ./vm.nix ];
    };

    # ✅ Your apps
    packages.${system} = {
      generate-clab-config =
        pkgs.writeShellApplication {
          name = "generate-clab-config";
          runtimeInputs = [ pythonEnv ];
          text = ''
            exec ${pythonEnv}/bin/python3 ${./generate-clab-config.py} "$@"
          '';
        };
    };

    apps.${system}.generate-clab-config = {
      type = "app";
      program =
        "${self.packages.${system}.generate-clab-config}/bin/generate-clab-config";
    };
  };
}
