# Boredroom

A leaderboard for the daily puzzle games your friends already play — Wordle,
Connections, Strands and the long tail of obscure ones. Instead of pasting
results into a WhatsApp group and losing them in the scroll, you share them to
Boredroom, and your rooms keep the streaks, rankings and bragging rights.

## Status

UX is locked (v8). The parser reads 26 games. The server (milestone 1, plus today and
minutes from milestone 2) and a first slice of the web app are live at boredroom.shmk.dev:
sign-in, boards and invites, pasting, the agenda, minutes, your games, and claiming an
imported seat. Review, the game screen and memos come next.

## Layout

```
server/          Flask backend (a uv project)
  boredroom/     the package; parser/ turns pasted share texts into results
  tests/         server tests, including a regression run over the chat export
  migrations/    alembic
  scripts/       corpus.py (parser report over an export), import_chat.py (seed a board)
web/             the PWA (React + Vite + TS); its tests live inside it
build/           Dockerfiles and build scripts (see build/README.md)
tests/           end-to-end tests across server and web (none yet)
docs/            decisions, specs, UX
research/        private source material (gitignored)
```

```
cd server
uv run pytest                          # tests
uv run python scripts/corpus.py        # parser report over ../research/soup_export.txt
../build/dev-db.sh start                # dev postgres on 127.0.0.1:5433
uv run alembic upgrade head
uv run flask --app "boredroom.app:create_app()" run --debug -p 5078   # api on :5078

cd web && npm install && npm run dev   # app at http://localhost:5173 (proxies /api to :5078)
```

Google sign-in in development needs `GOOGLE_OAUTH_CLIENT_ID` in the Flask server's
environment, and `http://localhost:5173` as an authorized JavaScript origin.

**Deploy (homeserver):** changes go to stage first (`build/deploy.sh stage`, stage-boredroom.shmk.dev), then `build/deploy.sh promote` puts the tested image in production; see build/README.md. Production: `bea build boredroom` builds `boredroom:latest` via
`build/build-docker-image.sh`. It runs as the `boredroom` service in yams on port 5077
(172.60.0.60), public at boredroom.shmk.dev through the Cloudflare tunnel, with its
Postgres as `boredroom-db` (172.60.0.61). The image serves the API and the built web app,
and migrates the database on boot. To seed a board from an export:
`docker cp export.txt boredroom:/tmp/x.txt && docker exec boredroom python scripts/import_chat.py /tmp/x.txt --chair NAME`.

- [`docs/ux/boredroom-ux.html`](docs/ux/boredroom-ux.html) — design philosophy, UX
  requirements, core flows and screen mockups (also published as an artifact)
- [`docs/VOICE.md`](docs/VOICE.md) — brand voice and nomenclature (agenda, the Chair,
  tenure, the daily bored meeting…)
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — what's been decided so far and why
- [`docs/OPEN-QUESTIONS.md`](docs/OPEN-QUESTIONS.md) — what still needs an answer

## Core objects

- **Games** — the library: name, link, when the puzzle resets, how a shared
  result is scored.
- **Rooms** — persistent groups of friends (admins + members) that track a set
  of games.
- **Results** — one person's result for one puzzle. Belongs to the person, not
  the room, so one share counts in every room tracking that game.
