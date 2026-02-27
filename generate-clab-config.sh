#!/usr/bin/env bash
set -euo pipefail
nix run .#generate-clab-config
