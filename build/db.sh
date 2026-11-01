#!/usr/bin/env bash
set -euo pipefail

# Data tools for the deployed databases (both live in the boredroom-db container).
#   build/db.sh [--prod] COMMAND      default target: stage
#
#   snapshot [NAME]   save the whole database to snapshots/<target>-NAME.dump (default: a timestamp)
#   restore NAME      put a snapshot back exactly (the app is stopped meanwhile)
#   list              list snapshots
#   empty             drop everything and migrate a fresh, empty database
#   forget USER...    delete people and everything theirs (a dry run unless --yes is given too)
#
# Production commands that destroy data ask you to type "production" first.

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
MAIN="$(git -C "$ROOT" worktree list --porcelain | sed -n '1s/^worktree //p')"
SNAPS="$MAIN/snapshots"   # one folder for every worktree: the main checkout's
DBC=boredroom-db
TARGET=stage
if [[ "${1:-}" == "--prod" ]]; then TARGET=prod; shift; fi
if [[ "$TARGET" == prod ]]; then DB=boredroom; APP=boredroom; else DB=boredroom_stage; APP=boredroom-stage; fi
ROLE="${DB}_app"   # each app logs in as its own role, which owns its database and nothing else
CMD="${1:-}"; shift || true

psql_() { docker exec "$DBC" psql -v ON_ERROR_STOP=1 -qU boredroom -d postgres -c "$1" >/dev/null; }  # admin work from outside the target db
confirm() {
  [[ "$TARGET" == stage ]] && return
  read -r -p "this replaces production data. type 'production' to go on: " ok
  [[ "$ok" == production ]] || { echo "stopped."; exit 1; }
}
stop_app() {  # if anything after this fails, the app still comes back up
  docker stop "$APP" >/dev/null
  trap 'docker start "$APP" >/dev/null 2>&1 || true' EXIT
}
fresh_db() {
  psql_ "DROP DATABASE IF EXISTS $DB WITH (FORCE)"
  psql_ "CREATE DATABASE $DB OWNER $ROLE"
  psql_ "REVOKE CONNECT, TEMPORARY ON DATABASE $DB FROM PUBLIC; GRANT CONNECT, TEMPORARY ON DATABASE $DB TO $ROLE"
}
wait_app() {
  for _ in $(seq 60); do
    [[ "$(docker inspect -f '{{.State.Health.Status}}' "$APP" 2>/dev/null)" == healthy ]] && return
    sleep 1
  done
  echo "$APP didn't come up healthy; check its logs" >&2; exit 1
}

case "$CMD" in
  snapshot)
    mkdir -p "$SNAPS"
    f="$SNAPS/$TARGET-${1:-$(date +%Y%m%d-%H%M%S)}.dump"
    docker exec "$DBC" pg_dump -U boredroom -Fc "$DB" > "$f"
    echo "saved $f ($(du -h "$f" | cut -f1))" ;;
  restore)
    f="$SNAPS/$TARGET-${1:?which snapshot? see: build/db.sh list}.dump"
    [[ -f "$f" ]] || { echo "no $f" >&2; exit 1; }
    confirm
    stop_app
    fresh_db
    docker exec -i "$DBC" pg_restore -U boredroom -d "$DB" --no-owner --role="$ROLE" < "$f"
    docker start "$APP" >/dev/null && wait_app
    echo "restored $f into $DB" ;;
  list)
    ls -1t "$SNAPS"/*.dump 2>/dev/null | xargs -r -n1 basename || true ;;
  empty)
    confirm
    stop_app
    fresh_db
    docker start "$APP" >/dev/null && wait_app   # the app migrates on boot
    echo "$DB is empty and migrated" ;;
  forget)
    docker exec "$APP" python scripts/forget.py "$@" ;;
  *)
    sed -n '4,14p' "$0"; exit 1 ;;
esac
