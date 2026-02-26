#!/usr/bin/env bash
(cd ~/github/network-solver; nix run .#compile-and-solve -- ../network-compiler/examples/single-wan/inputs.nix) | tee ./output-network-solver.json > /dev/null
