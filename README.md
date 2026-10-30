# Boredroom

A leaderboard for the daily puzzle games your friends already play — Wordle,
Connections, Strands and the long tail of obscure ones. Instead of pasting
results into a WhatsApp group and losing them in the scroll, you share them to
Boredroom, and your rooms keep the streaks, rankings and bragging rights.

## Status

UX is locked (v8). The parser is built: 26 games, tested against the soup export.

## Layout

```
server/          Flask backend (a uv project)
  boredroom/     the package; parser/ turns pasted share texts into results
  tests/         server tests, including a regression run over the chat export
  scripts/       dev scripts (corpus.py: measure the parser against an export)
  demo/          early paste-box demo (temporary: deployed until the web app replaces it)
web/             the PWA frontend (not started); its tests live inside it
build/           Dockerfiles and build scripts (see build/README.md)
tests/           end-to-end tests across server and web (none yet)
docs/            decisions, specs, UX
research/        private source material (gitignored)
```

```
cd server
uv run pytest                          # tests
uv run python scripts/corpus.py        # parser report over ../research/soup_export.txt
uv run python demo/app.py              # demo at http://127.0.0.1:5077
```

**Deploy (homeserver):** `bea build boredroom` builds `boredroom:latest` via
`build/build-docker-image.sh`. It runs as the `boredroom` service in yams on port 5077
(172.60.0.60), public at boredroom.shmk.dev through the Cloudflare tunnel. Today that
image is the early parser demo; the web app replaces it behind the same name and port.

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
