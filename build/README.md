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

## Files

| file | what |
|---|---|
| `build-docker-image.sh` | builds `boredroom:latest`; `bea build boredroom` runs it |
| `server.Dockerfile` | the app image (context: the repo root) |
| `server.Dockerfile.dockerignore` | docker reads it from beside the Dockerfile |
| `dev-db.sh` | the development postgres container (start, stop, reset) |
