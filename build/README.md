# Build

Everything that turns the repo into something deployable lives here, apart from
the code.

## What's permanent and what isn't

**Permanent (the deployment):** one image, `boredroom:latest`, built by
`build-docker-image.sh` (which `bea build boredroom` calls). The homeserver runs it as
the `boredroom` container on port 5077, public at boredroom.shmk.dev through the
Cloudflare tunnel. These names stay when the content changes, so the homeserver config
and the tunnel never need touching.

**What's in it:** `server.Dockerfile` builds `web/` in a node stage, then packages the
Flask app (the API, serving the built web app with an index.html fallback) under
gunicorn on 5077. It runs `alembic upgrade head` before starting. The database is the
`boredroom-db` container (postgres:16), configured in the homeserver repo.

## Stage and production

Two instances run side by side from the same Postgres container (`boredroom-db`):

| | production | stage |
|---|---|---|
| url | boredroom.shmk.dev | stage-boredroom.shmk.dev |
| container, port | `boredroom`, 5077 | `boredroom-stage`, 5079 |
| image | `boredroom:latest` | `boredroom:stage` |
| database | `boredroom` | `boredroom_stage` |

Every change goes to stage (`build/deploy.sh stage`). Production only moves when it's
been checked there: `build/deploy.sh promote` retags the tested stage image as
`latest`, so production runs exactly what was tested. Stage shows a "stage" badge.

Test data lives on stage and is cheap to clear: `build/db.sh reset` (back to soup's
history), or `snapshot` before and `restore` after. `forget USER --yes` deletes one
person, on either instance (`--prod`), which is also how deletion requests are handled.

## Files

| file | what |
|---|---|
| `build-docker-image.sh` | builds `boredroom:latest`; `bea build boredroom` runs it |
| `server.Dockerfile` | the app image (context: the repo root) |
| `server.Dockerfile.dockerignore` | docker reads it from beside the Dockerfile |
| `dev-db.sh` | the development postgres container (start, stop, reset) |
| `deploy.sh` | `stage`, `promote` (stage image → production) or `prod` |
| `db.sh` | `snapshot`, `restore`, `list`, `reset`, `forget` on stage, or production with `--prod` |
