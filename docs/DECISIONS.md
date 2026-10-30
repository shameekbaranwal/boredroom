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
