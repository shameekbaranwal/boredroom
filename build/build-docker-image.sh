#!/usr/bin/env bash
set -euo pipefail

# Builds boredroom:latest, the image the homeserver runs as the `boredroom` container.
# It's the app: the Flask API plus the built web/ (build/server.Dockerfile, context: repo root).
# Consumed by `bea build boredroom`; also runnable standalone.
# Tests are not run here: run `cd server && uv run pytest` first.

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_TAG="${1:-boredroom:latest}"

docker build -t "$IMAGE_TAG" -f "$ROOT/build/server.Dockerfile" "$ROOT"

printf 'built image %s\n' "$IMAGE_TAG"
