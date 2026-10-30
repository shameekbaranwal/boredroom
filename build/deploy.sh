#!/usr/bin/env bash
set -euo pipefail

# Stage first, then promote the exact same image to production.
#   build/deploy.sh stage      build boredroom:stage, recreate boredroom-stage
#   build/deploy.sh promote    tag boredroom:stage as boredroom:latest, recreate boredroom
#   build/deploy.sh prod       build boredroom:latest directly (what `bea build boredroom` does)
# Run `cd server && uv run pytest` first; nothing here runs tests.

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

recreate() {  # a restart alone keeps the old image; the service has to be recreated
  if command -v bea >/dev/null; then bea yams restart "$1"
  else echo "now recreate the $1 service so it runs the new image"; fi
}

case "${1:-}" in
  stage)   "$ROOT/build/build-docker-image.sh" boredroom:stage && recreate boredroom-stage ;;
  promote) docker tag boredroom:stage boredroom:latest && echo "boredroom:latest is now the stage build" && recreate boredroom ;;
  prod)    "$ROOT/build/build-docker-image.sh" boredroom:latest && recreate boredroom ;;
  *) echo "usage: $0 stage|promote|prod" >&2; exit 1 ;;
esac
