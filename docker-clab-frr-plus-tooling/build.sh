#!/usr/bin/env bash
set -e

IMAGE=clab-frr-plus-tooling:latest
DIR="$(cd "$(dirname "$0")" && pwd)"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "[clab] building local FRR tooling image..."
    docker build -t "$IMAGE" "$DIR"
fi
