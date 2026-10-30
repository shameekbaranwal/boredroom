# UX notes

Functional requirements for the UX-screens round (from feedback on 2026-10-28),
with the design response we'll mock up. Visual direction: Spreadsheet (see
DECISIONS.md).

## 1. Review chart scales to 10+ members

The group has 10+ people and a different subset plays each day, so grouped bars
(one bar per member per day) break down past ~4 people.

- Default chart: **one bar per day = board total** (or members present), stacked or
  plain, with "you" marked inside it. Fits any board size.
- **Member grid** (heatmap): rows = members, columns = days, cell = items done or
  the score. Reads at 15+ rows, and a sheet layout suits it naturally.
- Tap a day → that day's standings list (scrolls; no legend needed).
- Pick members to compare → overlay up to ~3 highlighted members; everyone else
  stays as a faint band.
- Member colors come from a generated palette (m1–mN), never hand-picked per
  member.

## 2. The query bar (the "fx" bar) is real

Every screen's top bar shows the query that produced the view and is editable.
- It's a **structured filter bar**, not free-text SQL: tokens like
  `board: soup daily · game: connections · period: week · stat: mistakes`.
  Tapping a token offers its options; typing narrows them (autocomplete).
- Changing the UI (tabs, chips, chart taps) rewrites the bar, and editing the bar
  changes the UI. Same state, two views.
- Per screen: agenda (`today`, `board`, `unfiled only`), review (game, period,
  stat, members), minutes (game, puzzle), library (search, category, reset),
  you (board, stat).
- Its *display* is themeable: spreadsheet shows `=review(…)`, Night Ledger shows
  `select …`, other themes show plain chips. Underneath it's one query model.
- Shareable: a query is a URL (`/review?game=connections&period=week`).

## 3. Switching boards, guests and sync

- Board switcher always one tap away (header title → list of your boards, with
  each board's "N of M done" today).
- **Signed in:** results belong to the person, so one filing appears in every
  board whose agenda has that game. No duplicates, nothing to sync.
- **Guest seats:** a device can hold several guest seats (one per board joined
  without signing in). The client keeps every seat's token, so on filing it
  **fans out**: it posts the result to each seat whose board has that game. Cheap
  to build, works offline-first, and it's what users will expect.
- Signing in later **claims** the device's guest seats into one account (history
  merged, dedupe by game + puzzle key).
- Guest seats on *other* devices can only merge by explicit "move your seat"
  linking (existing device-linking flow).

## 4. One review dashboard: daily, weekly, all-time

- One screen, not three. Controls: **period** (today / week / month / all time),
  **game** (all games or one), **stat** (items done, wins, average score, best,
  tenure…; options depend on the game's score type).
- Sensible defaults: this week · all games · items done.
- Each combination shows: standings, the chart (see 1), and memos (see 5).
- Per-game stats come from the parser's score type (guesses, mistakes, points…),
  so new games get stats for free.

## 5. Memos are a core feature

Memos are short generated notes that turn numbers into board gossip. They show up
in the review, the minutes, notifications and the daily bored meeting recap.
- **Types:** hostile takeover, on a PIP, tenure milestones and broken tenure,
  perfect attendance, personal bests, missed targets, first to file, "the board is
  concerned" (a bad streak), photo finishes (a tie, or a 1-point gap), comebacks,
  "file N more to take #1".
- Each memo is a template + a trigger rule + data, rated by how interesting it is.
  A screen shows the top one or two, never a wall.
- Memos are clickable: one opens the review query that backs it.
- Tone follows VOICE.md: dry, never mean, lowercase.

## 6. Richer agenda presence

The "ivan, judy present" line under each item gets richer without cluttering:
- **Avatar stack** of who has filed (max 3 + "+7"), plus the board's **best so far**
  ("best: ivan · 1 mistake") once you've filed (spoiler-safe until then).
- An item nobody has played yet says so ("no one yet — be first").
- Tap the line → that game's minutes.
- With a 10+ board this stays one line, and the counts carry it.
