# Server spec (draft 1, 2026-10-30)

The parser turns pastes into results. The server keeps them: who filed what, on which
boards it counts, and what each member is allowed to see. This spec covers the data
model, the API, and how "today", visibility and daily wins are computed.

Part 6 lists the open choices, numbered so they can be answered by number. Each one says
what I'd pick.

## 1. Milestones

1. **Filing works.** Schema and migrations, people and boards, agendas, and
   `POST /pastes` (parse → merge → store). The soup export is imported as seed data.
2. **Boards read well.** Today (the agenda), minutes, review (today and all time), one
   game, and memos. Visibility is enforced on the server.
3. **The web app.** The v8 screens as a PWA, with the share target on Android.
4. **Swap the deploy.** The app replaces the demo behind `boredroom:latest` and port
   5077 (see build/README.md), plus a Postgres container. Then reminders.

Milestones 1 and 2 are server-only. Each ends with tests over the soup export.

## 2. Principles carried over

- **Results belong to people, not boards.** One filing counts on every board where the
  game is on that member's agenda.
- **A result is keyed by `(person, game, puzzle)`.** The puzzle key comes from the
  parser (a number, an ISO date, or the Wiki page pair).
- **The parser's output is stored as is, plus the raw paste,** so a better parser can
  re-parse history later (`parser` holds the version).
- **Visibility is the server's job.** Detail and spoiler fields are stripped from any
  response unless the requester has filed that puzzle. The client never receives what it
  shouldn't show.
- **Read paths compute, not store.** Standings, daily wins and memos are computed per
  request from results. At soup's scale (about 50 results a day) that's milliseconds.
  Cache later if a bigger board needs it.

## 3. Data model

```
person        id, username, kind (guest | account), tz, created_at
session       id, person_id, token_hash, device, created_at, last_seen      (guest seats too)
board         id, name, slug, chair_id, settings jsonb, created_at
                settings: late_filing, join (link | approval), …
membership    board_id, person_id, nickname, role (chair | member), joined_at, left_at
board_game    board_id, game_id, added_by, rules jsonb                       (the board's library)
                rules: ranked, ranker order, spoilers, late filing — overrides of the defaults
agenda        board_id, person_id, game_id, added_at                         (your games on that board)
paste         id, person_id, raw, received_at, source (paste | share | import)
result        id, person_id, game_id, puzzle_key, puzzle_day,
              outcome, metrics jsonb, fields jsonb, highlights text[], extras jsonb,
              comment, confidence, parser, filed_at, amended_at, withdrawn_at,
              paste_ids int[]                                                  unique (person_id, game_id, puzzle_key)
puzzle_day    game_id, puzzle_key, day                                       (wiki page pair → date)
seat_claim    board_id, import_name, person_id, status                       (soup history, see choice 6)
```

- **Games aren't a table.** The library is the parser registry in code. Boards refer to
  games by id (`krillion`). Board-private custom games come later as a `custom_game`
  table, using the unknown-game form.
- **`puzzle_day`** is the day a puzzle belongs to, for daily wins and the review. Number
  and date keys compute it from the game's anchor and reset. A Wiki page pair takes
  the day of the first filing of that pair (PARSER.md choice 4).
- **Late filing** is computed: `puzzle_day` is before the filer's current puzzle at
  `filed_at`.

## 4. How the reads work

- **Today, for one member on one board:** for each game on their agenda, the current
  puzzle comes from the registry and their tz. Open means not filed. The reset countdown
  comes from the game's reset rule. Filed games show your place.
- **Minutes, one game, one puzzle:** the results of members who play that game, ranked
  by the board's ranker (`rank()` from the parser package). Fields are filtered by
  visibility for the requester.
- **Daily wins:** for each day and game, place 1 among at least 2 present counts as a
  win. A tie shares the win.
- **Memos** are rules: each is a function from (board, day) to zero or more memos with
  a kind, member, text, number and link. They're registered like games, so adding one
  is one function.

## 5. API

JSON under `/api/v1`. The client sends a bearer token (one per seat).

| method | path | what |
|---|---|---|
| POST | `/pastes` | parse and file. Returns per-result events (filed, merged, duplicate, conflict) and any unknown-game prefill |
| POST | `/results/{id}/replace` | answer "replace?" with a paste id |
| DELETE | `/results/{id}` | withdraw |
| GET | `/me` | person, seats, boards |
| GET | `/boards/{slug}/today` | agenda: open games by reset, top memos, filed games with your place |
| GET | `/boards/{slug}/minutes/{game}/{puzzle}` | one puzzle's results, visibility-filtered |
| GET | `/boards/{slug}/review?period=today\|all\|week\|month` | daily wins and per-game rows |
| GET | `/boards/{slug}/games/{game}` | one game: stats, ranking by average, head-to-head |
| GET | `/boards/{slug}/meeting?day=` | all memos for a day |
| POST | `/boards` · `/boards/{slug}/join` · `/boards/{slug}/invite` | create, join, invite link |
| PUT | `/boards/{slug}/agenda/{game}` · DELETE likewise | your games |
| PATCH | `/boards/{slug}/me` | nickname |
| PATCH | `/boards/{slug}/rules/{game}` | chair: per-game rules |
| GET | `/boards/{slug}/export/whatsapp?scope=` | the WhatsApp text for a result, minutes or the review |

## 6. Open choices

1. **Database access.**
   - (a) **SQLAlchemy 2 ORM with Alembic migrations.**
   - (b) SQLAlchemy Core: tables and queries, no ORM objects.
   - (c) Raw SQL with psycopg.

   I'd pick (a). It's the standard Flask pairing, migrations come with it, and
   the queries here are simple.

2. **Signing in.** Guests are real server accounts with no email (decided 2026-10-27).
   The question is how an account signs in:
   - (a) **Sign in with Google.** No passwords, and everyone in soup has an Android
     phone.
   - (b) A magic link by email. Needs an email sender.
   - (c) Passkeys. The nicest long term, but the most work and the least familiar.
   - (d) Username and password.

   I'd pick (a), with guests able to claim their seats into an account later. Google
   OAuth needs a Google Cloud OAuth client for `boredroom.shmk.dev`, and you'd have to
   create that.

3. **Web app stack.**
   - (a) **A JSON API plus a small SPA:** Svelte with Vite, built into static files
     Flask serves. Good for a PWA (offline cache, share target), the formula-bar and
     drill-in-tab interactions, and a native Android app could use the same API later.
   - (b) Server-rendered Jinja plus htmx. One codebase and fast to build, but awkward
     for offline and the richer interactions.
   - (c) React with Vite. Same shape as (a), heavier.

   I'd pick (a).

4. **Where results show up.** "Results belong to people" means filing krillion shows
   on every board where krillion is on your agenda. Should a member be able to keep a
   result off one board? I'd say no for v1: your agenda already decides it.

5. **Metrics as JSON or columns.** I'd keep them as jsonb, the parser's shape as is,
   since games differ. Ranking and averages run in Python over a board's results,
   which is small.

6. **Seeding soup from the export.** The import files every result under a placeholder
   member per sender ("ivan", "+65 …"). When a friend joins soup, they claim
   theirs ("which of these is you?") and the history moves to their account. I'd
   do it that way, so soup starts with 20 days of records and tenure. The import
   stays an internal tool (decided).

7. **Tests.** Against a real Postgres (a throwaway container per test run), or SQLite?
   I'd use Postgres. jsonb and array columns behave differently in SQLite, and a
   container is cheap here.

8. **Timezone per person.** Taken from the browser on first use and editable in "you".
   Local-midnight games use it. I'd store it on the person, not per seat.

## 7. Testing

- Unit tests per query (today, minutes, review, daily wins, visibility) on small
  hand-made boards.
- An import test: load the soup export, then check known facts. For example, daily
  wins per member over the 20 days, the maptap record (964), and that a member who
  hasn't filed a puzzle sees no routes.
- API tests through Flask's test client, including the token and visibility rules.
