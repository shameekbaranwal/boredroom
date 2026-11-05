# To do

What's worth building next, roughly in order. Each line says what it is and how it'd be done.
Settled "no"s are at the bottom so they don't come back.

## On stage now

- **Pastes: check first or file at once.** `person.paste_check`; off skips the clerk's look and files straight
  away (nothing readable still shows the look).

## Next

- **Front door.** A landing page for visitors who arrive without an invite (today they get a bare guest
  seat), with a short walkthrough of the flow (paste → minutes → memos) and "start a board".
- **Wrapped.** A personal look back for anyone with more than a month of results: favourite games, best
  days, tenure, records. One shareable card; reads only what `result` already has.
- **Timezones, lite.** Check resets and puzzle days for a board spread across zones (the app has only run
  on IST) and fix what's off. No new settings.
- **Parked state-transition fixes.** Guest → existing Google account orphan, refile timing, claim
  round-trip, conflict state (from the earlier audit).

## Later

- **iPhone shortcut.** iPhones keep web apps out of the share sheet, so a Shortcut posts the share text to
  `POST /shortcut` with a filing-only key. Built and parked on the `ios-shortcut` branch; needs an iPhone
  to make a one-tap iCloud link (key as its import question) before it's worth shipping.
- **Teach the clerk.** Paste an unknown game 2–3 times; a parser is drafted from the examples and the
  chair approves it for the board. Opens the app to games we haven't written parsers for.
- **Analytics, lite.** An admin-only page of anonymous counts (people and boards active, pastes a day,
  games played). No tracking of screens or clicks.
- **Moving off the homeserver.** Only once outsiders show up. Same image and Postgres on a small VM
  (Cloudflare tunnel moves with it); backups to object storage instead of local disk.

## Maybe

- **Rivalries, only as memos.** A memo when two people keep trading places on a game; not a concept of its
  own.

## Ideas to weigh

From a round of research on how groups share daily puzzles; not judged yet.

- **Forward guidance.** Call your score before you play ("wordle in 4"); the minutes say whether you beat it.
- **After-hours thread.** A per-game, per-day thread that opens only once you've filed: the spoiler talk
  the group chat can't have.
- **Circulate the minutes.** One tap turns today's minutes into a chat-ready card, with who hasn't filed.
- **Portfolios.** Whoever leads a game over a rolling 30 days holds it ("head of geography"); a change is a
  memo.

## Settled no

- The grid view (overkill for now), monthly awards, seasons, and filing by reading the group chat.
