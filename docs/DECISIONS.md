# Decisions

Running log. Newest at the bottom. Each entry: what, and why.

## 2026-10-26 — Working name is "Boardle"

Placeholder. Revisit before anything public-facing.

## 2026-10-26 — No native iOS app

The $99/yr Apple Developer fee isn't worth it for a small app. iPhone users get
the web app. Most of the friend group is on Android anyway.

## 2026-10-26 — Clients: Android + web

The web app is the general-purpose client (desktop, iPhone, anything). Android
users additionally get a share-sheet target so logging a result is one gesture.
Whether the Android client is an installed PWA or a native build is still open
(see OPEN-QUESTIONS.md #1).

## 2026-10-26 — Backend: Flask + Postgres

Simple, familiar, enough for this. Self-hosted on the homeserver to start, but
kept cloud-portable: production isn't assumed to stay self-hosted.

## 2026-10-26 — Results belong to people, not rooms

One shared result counts in every room that tracks that game. Rooms are views
over their members' results, not containers of them.

## 2026-10-26 — Results are keyed by puzzle, not by clock

A result is identified by `(person, game, puzzle)`, where puzzle is the game's
own number when it has one (`Wordle 1,592`) and the date in the game's reset
timezone otherwise. Friends in different timezones then compare the same puzzle,
and duplicates are impossible.

## 2026-10-26 — WhatsApp bot is parked

A bot living in the group (posting resets, a midnight leaderboard, reading
pasted results) is a good idea but not the core. Revisit after v1.

## 2026-10-26 — Brand voice: corporate meeting × word games

The app's copy plays your friend group as an over-serious company board that meets
daily about puzzles. Rooms are boredrooms, the admin is the Chair, the daily recap is
the minutes, a streak is tenure, last place is "on a PIP", taking #1 is a hostile
takeover. Members are **members** or **board members**, never "directors". Keep it to
a few lines of copy, not every label; buttons stay plain. Full glossary and rules
in docs/VOICE.md.



## 2026-10-26 — Name: Boredroom

Replaces the "Boardle" placeholder (a daily chess puzzle already uses that name).
Boardroom → bored: the corporate voice in one word, and the app's core unit is
already a room. Reads correctly written, which is how people mostly meet it
(store, icon, links). "The daily bored meeting" is the recap. `boredroom.app` is a
small unrelated meeting-bingo web toy; no store listing or trademark found. Domain
not bought yet: `boredroom.dev` / `.fun` were free on 2026-10-26, or use a subdomain.

## 2026-10-27 — Answers to the open questions (artifact comments)

- **Clients:** PWA only for v1 (Android share target + web everywhere). A native
  Android app is a later step.
- **Spoilers:** hidden until you've filed the same puzzle. Needs parsers that know
  which part of a share is the grid/answer and which is safe to show.
- **Streaks:** several kinds, each named in the voice (see VOICE.md "Streaks").
- **Rankings:** no cross-game normalization in v1. The one cross-game number is
  **how many agenda items you did that day** ("productivity").
- **Late filing:** allowed by default; the Chair can turn it off per board.
- **Joining:** the Chair controls it. Invitation link joins directly by default; the
  Chair can switch on approval.
- **Agenda:** board members can add games; the Chair can remove games and members.
- **Custom games:** board-private for now.
- **Guests:** real server accounts with no email; local storage is only a cache.
- **Notifications:** one evening reminder, **on by default**, sent only if you've
  filed nothing at all that day.
- **Audience:** friends-only for v1, but design so a public launch needs no rework
  (no hard-coded single tenant, global library separate from board-private games,
  rate limits and reporting hooks planned even if unused).
- **Hard mode / variants:** a badge on the same result, not a separate leaderboard.
- **Voice:** "missed target" for a failed puzzle is in; guests stay "guests"
  ("contractors" rejected). Expanding the nomenclature within the theme is welcome.
- **Launch games:** the 15 in docs/GAMES.md.

## 2026-10-28 — Order of work

1. **Visual design**: pick a direction (docs/design/directions.html).
2. **UX screens**: redo the mockups cleanly in the chosen direction.
3. **Dev**, starting with the **parser spec**: how game parsers are defined and
   extended, so a new game with an unfamiliar share format slots in without an
   overhaul, plus every edge case (variants, failures, edited/partial shares,
   multiple results in one paste, spoiler-safe fields).

The name-hunt notes were dropped from the repo; the outcome is the "Name: Boredroom"
entry above.

## 2026-10-28 — Lowercase house style

All in-app text is lowercase: names, board names, headings, stamps, notifications.
Sample data uses the board "soup daily" with members ivan and judy.

## 2026-10-28 — Visual direction (provisional) and themes

- **Leading direction: Spreadsheet.** Light mode as designed in round 3. Dark mode
  uses Night Ledger's palette (navy cells, mint for done, amber for open, mono
  numbers). Pending a final look in docs/design/directions.html.
- **Themes are a feature, not a one-off.** Users will eventually pick from the
  directions explored (Puzzle Page, Riso, Night, the crosses…), each with a light and
  dark pair. So the UI code, web and Android, must:
  - read only **semantic tokens** (surface, ink, muted, line, accent, ok/ok-ink,
    todo, note, tile colors g1–g7, member colors m1–mN, fonts for heading, body and
    numbers, radii), never raw colors;
  - treat **layout** as a theme property too: "sheet" (rows, gutter numbers, query
    bar, tabs) vs "free" (cards, pills). Components take a layout variant; screens
    don't branch per theme;
  - keep finishes (riso grain, glow, misregistration) as optional decoration
    layers that cost nothing when off;
  - define each theme once as data (JSON: tokens + layout + light/dark pair) that
    becomes CSS variables on web and a Compose theme on Android.

See docs/UX-NOTES.md for the functional requirements that came with this.

## 2026-10-30 — From the soup chat (see docs/CHAT-FINDINGS.md)

- **"Today" is per game:** a game's today is the user's current puzzle for it. Minutes,
  presence and review group by puzzle key, not calendar date. The agenda shows a live
  reset countdown per item and sorts open items by time to reset.
- **Your agenda vs the board's library:** each member picks the games they play from
  the board's library. Presence counts only members who play that game ("3/3 present").
- **Visibility:** scores, standings and presence are public before you file (the bait).
  Gameplay details (grids, routes, clues, paths) unlock once you've filed that puzzle.
  The parser marks which fields are details and which are spoilers per game (cryptic
  clue and wiki route are; the strands theme isn't).
- **Ranking:** each game has a ranker (metrics in order, direction, tiebreaks). Some
  games have no score; they count as played and produce no wins. Ties share a rank.
- **Cross-game standing:** daily wins (games you placed #1 in). No per-game weights.
  Review, minutes and memos are modular (rankers, views as queries, memos as
  independent rules) so this can change drastically later.
- **Review defaults to today.**
- **Filing:** late filing and editing your own result are allowed. Re-filing a puzzle
  asks to replace. Results show "filed late" / "amended".
- **Names:** a nickname per board, defaulting to the username.
- **WhatsApp stays the place for talk.** Boredroom-first, then forward: after filing,
  "send to soup" passes the original text on. Minutes can be shared to WhatsApp for
  one result, one game, or the review so far.
- **Chair rules per game** (ranked or logged, tiebreak order, spoilers, late filing),
  with sensible defaults.
- **Memos stay simple:** standings, highlights (krill, perfect, personal best), later
  records and rivalries.
- **Chat-export import** is an internal tool for seeding soup, not a user feature yet.
- **Agenda and reset clock lead the UI;** review stays central.
- **Voice:** "board" stays the word; "bored" only in a few spots (Boredroom, the daily
  bored meeting).

## 2026-10-30 — Navigation and review, second pass

- **Three tabs: agenda · review · you.** Minutes, a single game, and the daily bored
  meeting open as one temporary tab from whatever you tapped (a row, a memo, a record).
  The library ("your games") and the chair's board settings live under "you".
- **Home = agenda:** open games by time to reset, then the top memos (two, since 2026-11-01), then what
  you've filed with your place on each.
- **Memos are sheet rows:** a glyph for the kind, who, one line, the number that matters.
- **Review shows today and all time only.** Week and month stay reachable as values of
  the period token in the formula bar. Charts and the member × day grid are gone; a
  game opens as a drill-in (ranking by average, head-to-head, a 30-day strip).
- **Chair settings** need another pass later.

## 2026-10-30 — Parser spec, draft 1 review (see docs/PARSER.md part 6)

- Games are Python classes with declared metadata plus a small `extract()`; parsing runs
  on the server only for now.
- Lenient parsing with a confidence field (exact / inferred / partial). A partial result
  on a known game opens as a pre-filled form for the member to complete.
- Unknown games open a pre-filled form, count as played, and send us an "add this game"
  request.
- Wiki Game keyed by its page pair; MapTap's missing year = nearest to now.
- Strands: hints, then spangram position. Minute Cryptic: hints, then time when both
  have it.
- Spoiler fields are always wrapped when forwarded to WhatsApp.
- DailyOrbs: played only for now (ranking proposal pending a look at the game).
- Connections 3x3 Bonus dropped. Noillirk: bigger distance is better. Pyra games are
  three games. All tier-2 games ship in v1.

## 2026-10-30 — Repeat pastes merge

- Pasting a puzzle you've already filed merges when it's the same play with more detail
  (the Wiki route posted after the plain share). Duplicates are ignored, and a
  different result asks to replace. See docs/PARSER.md part 1.

## 2026-10-30 — Server stack (see docs/SERVER.md part 6)

- Flask + Postgres with SQLAlchemy 2 and Alembic. JSON API under `/api/v1`.
- Web app: React + Vite + TypeScript, chosen over Svelte so a React Native app later
  can share the API client, types and data hooks.
- Sign-in: Google, verifying ID tokens on the server, so hosting stays open
  (self-hosted now; Firebase or AWS possible). Guest tokens until the OAuth client
  exists.
- Soup's history is seeded by hand from the export, under placeholder members.

## 2026-11-01 — Fewer memos up front

The agenda carries at most two memos, the games stay the point of the page. The daily
bored meeting shows its eight biggest first (six until 2026-11-02, raised as new kinds arrived), and the rest behind "N more on the record".
Sending the meeting to the chat still sends every item.

## 2026-11-02 — More gossip

Sixteen more kinds of memo, so the meeting has more to say than records and tenures:
precedent (a highlight the board has never seen), bull run and coup (outright daily wins
in a row, and the day someone ends one), jinx (the same grid square for square, solves
only), unanimous (everyone tied, in place of a photo finish), clean sweep, rumour (one
daily win off #1), closing bell (filed in the last ten minutes), night shift (2–5am),
the board's 500th/1,000th result, quorum, the usual (the same score five days running)
and board member of the month (the best win rate, not the most wins). Then two more: rivalry
of the week (mondays: the two closest head-to-heads of the month, meeting only) and strong
quarter (a week's average well up on the week before; never the downward version). And perfect
attendance: all your regulars filed (games you filed on 10 of the 14 days before), 5, 10,
20, 30, 50, 100 days running. Not the whole agenda: the import put every game anyone ever
played on it, and no one in soup managed more than three days of that. Records say whose
they were and for how long. The small talk (interest 35 or less) is capped at three a
day, and the cheap ones carry cooldowns, so no one appears in it daily. Nothing is ever
about one person's miss.

## 2026-11-02 — Sorting the agenda

The agenda sorts in its formula bar, the way the review filters: =agenda(board, sort,
order). The usual (yours most filed, then the soonest reset), resets, my results,
popularity (the board's results over 30 days), busy today, my tenure and a–z, each either
way round. It sorts within each tab, so "to do" stays what's left. The choice goes with
your account (me.agenda_sort), so every device you sign in on orders it the same way; it's
picked where it's used, never on a settings screen. A row says what it's sorted
by when it doesn't already.

## 2026-11-02 — Skipping a game till it resets

Any open game can be sat out for today: open its row, "skip till reset". It leaves "to do"
on every board you play it on, and comes back by itself when the game resets, because a skip
is kept against the game day (person, game, day), not as a flag to remember to clear. A
toast offers undo. Skipped games fold away like a spreadsheet's hidden rows: one thin strip
at the foot of "to do" (the row numbers jump past them), and tapping it lists each with when
it's back and the ways out: put it back, play it anyway, or leave them be.
Filing a result wins over a skip. A skip doesn't hold a tenure: it still lapses at reset.
