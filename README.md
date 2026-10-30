# Boredroom

A leaderboard for the daily puzzle games your friends already play — Wordle,
Connections, Strands and the long tail of obscure ones. Instead of pasting
results into a WhatsApp group and losing them in the scroll, you share them to
Boredroom, and your rooms keep the streaks, rankings and bragging rights.

## Status

Pre-build. We're locking UX and requirements before any architecture or code.

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
