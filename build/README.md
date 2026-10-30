# Build

Everything that turns the repo into something deployable lives here, apart from
the code.

## What's permanent and what isn't

**Permanent (the deployment):** one image, `boredroom:latest`, built by
`build-docker-image.sh` (which `bea build boredroom` calls). The homeserver runs it as
the `boredroom` container on port 5077, public at boredroom.shmk.dev through the
Cloudflare tunnel. These names stay when the content changes, so the homeserver config
and the tunnel never need touching.

**Temporary (what's in the image today):** `demo.Dockerfile` packages the early
parser demo (`server/demo/`) for friends to try. It's not the app.

## When the web app lands

- `server.Dockerfile` replaces `demo.Dockerfile`: the Flask app (API, and the built
  `web/` assets as static files) under gunicorn, still on port 5077.
- `build-docker-image.sh` builds that instead (a web build stage if `web/` needs one).
- Delete `demo.Dockerfile`, its `.dockerignore`, and `server/demo/`.

## Files

| file | what |
|---|---|
| `build-docker-image.sh` | builds `boredroom:latest`; `bea build boredroom` runs it |
| `demo.Dockerfile` | temporary: the parser demo image (context `server/`) |
| `demo.Dockerfile.dockerignore` | docker reads it from beside the Dockerfile |
