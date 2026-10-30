#!/usr/bin/env bash
set -euo pipefail

# Local development only: Postgres for running the server and its tests, on
# 127.0.0.1:5433. The credentials are dev-only; production gets its own.
#   build/dev-db.sh          start (creates the container the first time)
#   build/dev-db.sh stop     stop it
#   build/dev-db.sh reset    delete it and its data

NAME=boredroom-dev-db
case "${1:-start}" in
  start)
    if docker container inspect "$NAME" >/dev/null 2>&1; then
      docker start "$NAME" >/dev/null
    else
      docker run -d --name "$NAME" --restart unless-stopped \
        -e POSTGRES_USER=boredroom -e POSTGRES_PASSWORD=boredroom -e POSTGRES_DB=boredroom \
        -p 127.0.0.1:5433:5432 -v boredroom-dev-db:/var/lib/postgresql/data postgres:16 >/dev/null
    fi
    until docker exec "$NAME" pg_isready -U boredroom -q; do sleep 1; done
    echo "postgres ready: postgresql+psycopg://boredroom:boredroom@127.0.0.1:5433/boredroom"
    ;;
  stop) docker stop "$NAME" >/dev/null && echo stopped ;;
  reset) docker rm -f "$NAME" >/dev/null; docker volume rm boredroom-dev-db >/dev/null; echo "deleted" ;;
  *) echo "usage: $0 [start|stop|reset]" >&2; exit 1 ;;
esac
