#!/usr/bin/env bash
set -euo pipefail

# Builds boredroom:latest, the image the homeserver runs as the `boredroom` container.
# For now it's the early parser demo (build/demo.Dockerfile); the real app replaces it
# behind the same tag, container and port (see build/README.md).
# Consumed by `bea build boredroom`; also runnable standalone.
# Tests are not run here: run `cd server && uv run pytest` first.

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_TAG="${1:-boredroom:latest}"

docker build -t "$IMAGE_TAG" -f "$ROOT/build/demo.Dockerfile" "$ROOT/server"

printf 'built image %s\n' "$IMAGE_TAG"
