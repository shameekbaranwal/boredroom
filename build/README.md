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

## Features and hotfixes

Each feature gets its own git worktree and branch, so a fix for production never waits on
work in progress. The main checkout stays on `master`, which is what production runs.

```
build/feature.sh new grid       # branch grid off master, in ../boredroom-grid
build/feature.sh stage grid     # put it on stage (deploy.sh stage, run from its worktree)
build/feature.sh list           # every feature, how far it is from master, what's on stage
build/feature.sh land grid      # it's approved: fast-forward master to it
build/deploy.sh promote         # production gets exactly the stage image
build/feature.sh done grid      # remove the worktree and branch
```

A hotfix is made and committed in the main checkout on `master`: `build/deploy.sh stage`
from there, check it, then `build/deploy.sh promote`. Stage then runs master, and
`build/feature.sh stage NAME` puts a feature back.

Whenever master moves, `promote` (and `prod`) rebase every feature onto it, uncommitted
work included, so the next feature promote keeps the fix. A feature that conflicts is left
as it was, with the command to rebase it by hand. `build/feature.sh rebase [NAME]` does
the same step by itself.

`promote` refuses unless the stage image was built from master's latest commit with
nothing uncommitted. Every image is labelled with the branch, commit and checkout it came
from, which is how it knows. `boredroom:latest` is only ever built from a clean master,
so `bea build boredroom` follows the same rule.

A new worktree links to the main checkout's `research/`, and snapshots from any worktree
go to the main checkout's `snapshots/`.

Test data lives on stage and is cheap to clear: `build/db.sh reset` (back to soup's
history), or `snapshot` before and `restore` after. `forget USER --yes` deletes one
person, on either instance (`--prod`), which is also how deletion requests are handled.

## Files

| file | what |
|---|---|
| `build-docker-image.sh` | builds `boredroom:latest` (clean master only) or a given tag, labelled with its source; `bea build boredroom` runs it |
| `server.Dockerfile` | the app image (context: the repo root) |
| `server.Dockerfile.dockerignore` | docker reads it from beside the Dockerfile |
| `dev-db.sh` | the development postgres container (start, stop, reset) |
| `deploy.sh` | `stage`, `promote` (stage image → production) or `prod` |
| `feature.sh` | feature worktrees: `new`, `stage`, `list`, `rebase`, `land`, `done` |
| `db.sh` | `snapshot`, `restore`, `list`, `reset`, `forget` on stage, or production with `--prod` |
