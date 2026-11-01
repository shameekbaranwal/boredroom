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

Every change goes to stage first. Production only moves when it's been checked there, and
only to master (below). Stage shows a "stage" badge.

## Branches: production is master

Production only ever runs master. Every change, a hotfix included, is a feature: a branch
cut from master in its own worktree, so several can be in progress at once.

```
build/feature.sh new fix-maps      # cut fix-maps from master, in ../boredroom-fix-maps
build/feature.sh stage fix-maps    # rebase it onto master, then put it on stage; repeat as it changes
build/feature.sh list              # every feature, how far it is from master, what stage runs
build/feature.sh promote fix-maps  # approved: merge into master, master onto production and stage
build/feature.sh done fix-maps     # remove the worktree and branch
build/feature.sh rebase [NAME]     # replay features onto master, any time
```

- **Stage** takes any branch, but only once it's rebased onto master (`stage` does that
  first). So a branch on stage is always a fast-forward of master, and its migrations
  come after master's.
- **Promote** checks that stage is running the branch's last commit with nothing
  uncommitted, which is the thing that was approved. It then fast-forwards master to it
  (the merge; push master afterwards) and runs `deploy.sh master`, which snapshots
  production's data and puts master on production and stage. Then it rebases the other
  features. A feature that conflicts is left as it was, with the command to finish by hand.
- **Migrations:** rebasing doesn't change a migration's `down_revision`. If master gained a
  migration after a feature wrote its own, both hang off the same parent, and `deploy.sh
  stage` refuses until the feature's is pointed at master's. It also refuses a branch that
  lacks the migration stage's database is on: another branch's. Restore a stage snapshot
  first (`build/db.sh list`, then `restore NAME`).
- **Images** are labelled with the branch, commit and checkout they were built from.
  `boredroom:latest` only builds from a clean master, so `bea build boredroom` follows
  the same rule.
- A new worktree links to the main checkout's `research/`. Snapshots from any worktree go
  to the main checkout's `snapshots/`.

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
| `deploy.sh` | `stage` (this checkout's branch) or `master` (production and stage) |
| `feature.sh` | feature worktrees: `new`, `stage`, `list`, `rebase`, `promote`, `done` |
| `db.sh` | `snapshot`, `restore`, `list`, `reset`, `forget` on stage, or production with `--prod` |
| `vapid.sh` | a VAPID key pair for one instance's reminders, written straight into its env file |
