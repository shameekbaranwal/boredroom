#!/usr/bin/env bash
set -euo pipefail

# Production only ever runs master. Stage runs any branch that's rebased onto master.
#   build/deploy.sh stage    build this checkout's branch as boredroom:stage, recreate boredroom-stage
#   build/deploy.sh master   snapshot production's data, then put master on production and stage
# Features are cut, staged and promoted with build/feature.sh; promote ends in `deploy.sh master`.
# Run `cd server && uv run pytest` first; nothing here runs tests.
#
# Stage refuses a branch that isn't rebased onto master, or whose migrations don't form one
# line (rebasing doesn't re-point a migration's down_revision: that's done by hand), or that
# lacks the migration stage's database is already on (another branch's: restore a snapshot).

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
MAIN="$(git -C "$ROOT" worktree list --porcelain | sed -n '1s/^worktree //p')"

recreate() {  # a restart alone keeps the old image; the service has to be recreated
  if command -v bea >/dev/null; then bea yams restart "$1"
  else echo "now recreate the $1 service so it runs the new image"; fi
}
label() { docker inspect -f "{{index .Config.Labels \"boredroom.$2\"}}" "$1" 2>/dev/null | sed 's/^<no value>$//' || true; }

revisions() { sed -nE "s/^revision[^=]*= *['\"]([^'\"]+)['\"].*/\1/p" "$1"/server/migrations/versions/*.py; }
heads() {  # revisions nothing else builds on
  local downs; downs=$(sed -nE '/^down_revision/{s/^[^=]*=//;p}' "$1"/server/migrations/versions/*.py | grep -oE "[0-9a-z_]{6,}" || true)
  revisions "$1" | grep -vxF -f <(echo "${downs:-^$}") || true
}
fits_stage_db() {  # the tree knows the migration stage's database is on
  local at; at=$(docker exec boredroom-db psql -U boredroom -d boredroom_stage -Atc "select version_num from alembic_version" 2>/dev/null || true)
  [[ -z "$at" ]] && return
  revisions "$1" | grep -qxF "$at" && return
  echo "stage's database is on migration $at, which $(git -C "$1" branch --show-current) doesn't have (another branch's)." >&2
  echo "put stage's data back first: build/db.sh list, then build/db.sh restore NAME (or build/db.sh empty)." >&2
  exit 1
}

case "${1:-}" in
  stage)
    branch=$(git -C "$ROOT" branch --show-current)
    git -C "$ROOT" merge-base --is-ancestor master HEAD ||
      { echo "${branch:-HEAD} isn't rebased onto master; first: build/feature.sh rebase $branch" >&2; exit 1; }
    h=$(heads "$ROOT")
    [[ $(wc -w <<<"$h") == 1 ]] ||
      { echo "migrations must form one line, but these are all heads: $(echo $h). point the newer one's down_revision at the other." >&2; exit 1; }
    fits_stage_db "$ROOT"
    "$ROOT/build/build-docker-image.sh" boredroom:stage && recreate boredroom-stage ;;
  master)
    master=$(git -C "$MAIN" rev-parse master)
    fits_stage_db "$MAIN"
    if [[ "$(label boredroom:stage commit)" == "$master" && "$(label boredroom:stage dirty)" == 0 ]]; then
      echo "stage already runs master (${master:0:7}): production gets that exact image"
    else
      "$MAIN/build/build-docker-image.sh" boredroom:latest   # refuses unless the main checkout is a clean master
      docker tag boredroom:latest boredroom:stage
    fi
    "$ROOT/build/db.sh" --prod snapshot "before-master-$(date +%Y%m%d-%H%M%S)"   # migrations run on boot; this is the way back
    docker tag boredroom:stage boredroom:latest
    recreate boredroom && recreate boredroom-stage
    echo "production and stage run master (${master:0:7})" ;;
  *) sed -n '4,8p' "$0" >&2; exit 1 ;;
esac
