#!/usr/bin/env bash
set -euo pipefail

# Builds boredroom:latest, the image the homeserver runs as the `boredroom` container.
# It's the app: the Flask API plus the built web/ (build/server.Dockerfile, context: repo root).
# Consumed by `bea build boredroom`; also runnable standalone.
# Tests are not run here: run `cd server && uv run pytest` first.
#
# Every image is labelled with the checkout it came from (boredroom.branch, .commit, .dirty,
# .tree), so promote can tell a committed master build from a feature's work in progress.
# Production (boredroom:latest) is only ever built from a clean master.

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_TAG="${1:-boredroom:latest}"

branch=$(git -C "$ROOT" branch --show-current)
commit=$(git -C "$ROOT" rev-parse HEAD)
dirty=0; [[ -z "$(git -C "$ROOT" status --porcelain)" ]] || dirty=1

if [[ "$IMAGE_TAG" == boredroom:latest && ( "$branch" != master || "$dirty" == 1 ) ]]; then
  echo "production builds come from a clean master; this is ${branch:-a detached HEAD}$( ((dirty)) && echo ' with uncommitted changes')." >&2
  exit 1
fi

docker build -t "$IMAGE_TAG" -f "$ROOT/build/server.Dockerfile" \
  --label boredroom.branch="$branch" --label boredroom.commit="$commit" \
  --label boredroom.dirty="$dirty" --label boredroom.tree="$ROOT" "$ROOT"

printf 'built image %s from %s at %s%s\n' "$IMAGE_TAG" "${branch:-HEAD}" "${commit:0:7}" "$( ((dirty)) && echo ' (uncommitted changes)')"
