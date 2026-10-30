#!/usr/bin/env bash
set -euo pipefail

# Builds the Boredroom server image from server/ using build/server.Dockerfile.
# Consumed by `bea build boredroom`; also runnable standalone.
# Tests are not run here: run `cd server && uv run pytest` first.

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_TAG="${1:-boredroom:latest}"

docker build -t "$IMAGE_TAG" -f "$ROOT/build/server.Dockerfile" "$ROOT/server"

printf 'built image %s\n' "$IMAGE_TAG"
