#!/usr/bin/env bash
set -euo pipefail

# Stage first, then promote the exact same image to production.
#   build/deploy.sh stage      build boredroom:stage from this checkout, recreate boredroom-stage
#   build/deploy.sh promote    snapshot production's data, tag boredroom:stage as boredroom:latest,
#                              recreate boredroom, then rebase every feature onto master
#   build/deploy.sh prod       build boredroom:latest directly (what `bea build boredroom` does)
# Run `cd server && uv run pytest` first; nothing here runs tests.
#
# stage builds whichever checkout runs it: a feature's worktree (build/feature.sh), or the
# main checkout on master for a hotfix. Only a stage image built from master's latest commit,
# with nothing uncommitted, can be promoted: a feature reaches master with build/feature.sh land.

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
MAIN="$(git -C "$ROOT" worktree list --porcelain | sed -n '1s/^worktree //p')"

recreate() {  # a restart alone keeps the old image; the service has to be recreated
  if command -v bea >/dev/null; then bea yams restart "$1"
  else echo "now recreate the $1 service so it runs the new image"; fi
}
label() { docker inspect -f "{{index .Config.Labels \"boredroom.$1\"}}" boredroom:stage 2>/dev/null | sed 's/^<no value>$//' || true; }

# master moved: replay every feature onto it, so the next promote of a feature keeps the fix
after_master_moves() {
  "$MAIN/build/feature.sh" rebase || echo "a feature couldn't be rebased (above); production is fine either way."
}

case "${1:-}" in
  stage)
    "$ROOT/build/build-docker-image.sh" boredroom:stage && recreate boredroom-stage ;;
  promote)
    master=$(git -C "$MAIN" rev-parse master)
    if [[ "$(label commit)" != "$master" || "$(label dirty)" != 0 ]]; then
      b=$(label branch); c=$(label commit)
      echo "stage isn't master's latest commit, so it can't go to production." >&2
      echo "  stage runs: ${b:-unknown} at ${c:0:7}$([[ "$(label dirty)" == 1 ]] && echo ', with uncommitted changes')" >&2
      echo "  master is:  ${master:0:7}" >&2
      echo "a feature: build/feature.sh land NAME. a hotfix: commit it on master, then build/deploy.sh stage from $MAIN." >&2
      exit 1
    fi
    "$ROOT/build/db.sh" --prod snapshot "before-promote-$(date +%Y%m%d-%H%M%S)"   # migrations run on boot; this is the way back
    docker tag boredroom:stage boredroom:latest && echo "boredroom:latest is now the stage build (${master:0:7})" && recreate boredroom
    after_master_moves
    [[ "$(label branch)" == master ]] && echo "stage is running master now. put a feature back with: build/feature.sh stage NAME"
    true ;;
  prod)
    "$ROOT/build/build-docker-image.sh" boredroom:latest && recreate boredroom
    after_master_moves ;;
  *) echo "usage: $0 stage|promote|prod" >&2; exit 1 ;;
esac
