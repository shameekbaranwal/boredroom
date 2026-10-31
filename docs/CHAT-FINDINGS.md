# What the soup chat says about the UX

Decisions taken from this are in DECISIONS.md (2026-10-30), which overrides the
suggestions here.

Source: the soup group's WhatsApp export, 11–30 Oct 2026. It is private: it stays in
`research/` (gitignored), and so do the tools that read it. This file keeps only what we
concluded. Nobody is quoted or named; where it helps, members are stand-ins (ivan, judy,
mallory…). About 11 members, 3,800 messages, 760 posted results across 25 games, and 268
screenshots. Six cheap-model passes read the chat in chunks; each finding was checked
against the export.

**The numbers to design for:** about 50 results a day. 15+ games are in play. The most
active member files 13–16 games a day, while one member files only MapTap. Most results
land between 9am and noon. One member lives in another timezone (UTC+8).

## 1. What we got wrong

1. **There is no single "today". Each game has its own day.** Krillion resets at 9:30,
   ANNO at 10:30, DailyOrbs at 2:30pm, and most of the rest at midnight. A member's
   hand-made leaderboard broke on exactly this. Most share texts carry a puzzle number
   but no date.
   → A game's "today" is its current puzzle. Minutes, presence and review periods group
   by puzzle key, not by calendar date. `resets 00:00` becomes a live countdown. The
   agenda sorts open items by the time left before they reset. Seeing every game's reset
   at a glance was also the first goal stated for the app.

2. **One number with one direction can't rank every game.**
   - The Wiki Game is steps, then time, and members disagree on which matters.
   - Connections and Strands have no number. Mistakes have to be read from the grid.
   - Fermi is lower-is-better, MapTap's final score is not the sum of its rounds, and
     Perceptle is a grade plus five sub-scores.
   - Exact ties are common: Krillion 340 = 340, Fermi 2.30× = 2.30×.

   → Each game gets an ordered list of metrics to rank by, and the board can reorder it.
   For the Wiki Game the default is steps, with time as the tiebreak, and the chair can
   flip that. Ties share a rank ("=2"), never an arbitrary order.

3. **"present" = "filed" is too blunt. Playing is opt-in per game.** The group says
   again and again that nobody has to play everything; people quit games, skip posting
   one, or are excused from it.

   "3/12 present" on Strands reads as shame when only three people ever play it.
   → Each member has their own agenda, the games they play. Presence is counted against
   the people who play that game: "3/3 present", not "3/12". The PIP and missed-target
   memos use the same count, so dropping a game never shows up as absence.

4. **The review defaults to the wrong period.** Feedback from the group: daily
   leaderboards are more fun than all-time ones, which hardly move.
   → The review defaults to **today**, then week. All time stays available but goes last.

5. **Counting "items done" across games just rewards volume.** The member who plays 15
   games wins every week. A member already proposed weighting games differently.
   → The cross-game stat becomes **daily wins**, a count of games you placed #1 in.
   Podiums (top-3 finishes) are the second view and items done is the third. All of
   them only count games you play.

6. **Spoilers live in the share text, not only in the grid.**
   - Strands puts its theme in the header (decided not a spoiler).
   - Minute Cryptic posts the clue.
   - The Wiki Game route is in brackets.
   - People hand-wrap results as `[Daily WIKI SPOILER]`, padded with hundreds of invisible
     characters (21 times).

   Direct feedback on our UX page: spoiler hiding should be per game, since games like
   Perceptle or Connections have little to spoil.
   → "Confidential" becomes a per-game setting, covering the whole result text (header,
   clue, route), not just the grid. The default is on for word and route games and off
   for score-only games.

7. **One evening reminder misses the moment that matters.** Puzzles vanish at reset, and
   people miss them by minutes.
   → The reminder becomes "krillion resets in 1h, you haven't filed", sent only for games
   on your own agenda. The evening digest becomes optional.

## 2. What we missed

8. **Corrections.** Wrong taps, accidental closes and re-dos are common, with deletes (25)
   and edits (29) throughout.

   → You can re-file, amend or withdraw your own result. The minutes show the stamp
   "amended" or "withdrawn". The chair can strike a result. Disputes stay in chat; the
   app just shows the stamp.

9. **Late filing is the norm, not an exception.** Yesterday's results get posted the next
   morning, and old re-shares need deduping.
   → Late filing is on by default and shows the stamp "filed late". A paste for a puzzle
   you already filed asks "replace?" instead of making a duplicate.

10. **Some games are just for fun.** Some are played for boredom, not competition. The
    member's hand-made leaderboard ranked only 7 of the roughly 19 games in play.
    → Each game has a flag, **ranked** or **logged**. Logged games show in the agenda
    and the minutes but don't count toward standings, PIPs or takeovers.

11. **The game list changes weekly.** Perceptle, Noillirk, Layers, three Pyra games,
    PetGuessr and Historydle all showed up in two weeks, each by someone pasting a
    result.
    → A paste the parser doesn't recognise offers "add *perceptle* to the agenda?". The
    form fills in from the link and the header, and the result files right away, counted
    as played until a parser for that game exists.

12. **Names don't match** (decided a non-issue: nickname per board, defaulting to the
    username). The group's leaderboard uses nicknames unrelated to contact names, contact
    names differ per phone, and one member is just a phone number. This matters for
    importing history (feature B).

13. **Special results matter more than the score.** A rare result beats a high score for
    bragging rights. A krill (🌟 in the grid) gets celebrated even on a low score. Others
    are Travle "+0 (Perfect)", Minute Cryptic "under the community par", Perceptle "S" and
    PlayPinDrop "New personal best!".
    → The parser pulls out a per-game **highlight** flag, and it feeds a memo:
    "ivan krilled (2 krills in 2 days)".

14. **Records and rivalries.**
    - Group records get noticed (a collective MapTap high score).
    - Members keep per-game feuds with one particular rival.
    - PlayPinDrop has a built-in head-to-head ("Rounds: 3-0").

    → Two new memos: board records (best ever, best combined day) and rivalries (a pinned
    head-to-head between two members, e.g. "mallory leads olivia 6–4 on maptap this
    month").

15. **What people want after playing is a reveal:** the optimal route, the answers, the
    path each person took.
    → Once a game's minutes are unlocked, they show what the result text contains: every
    Wiki Game route side by side, and each member's Travle path. We only show what was
    pasted and never fetch answers.

16. **Games' own streaks are in the share text**, e.g. "🔥 39 day streak". We keep our
    tenure (a streak of filing) and show the game's streak beside it, without merging the
    two.

17. **Out of scope, on purpose:**
    - **Screenshots** (268): no OCR for now; paste is the input.
    - **Cheating** (incognito retries, look-ups): we don't police it. A friends' board
      runs on trust, and corrections cover honesty.
    - **In-app chat:** the group wants talk to stay in WhatsApp, where it already is.
      This is what we assumed, so the gap to close is getting results back into
      WhatsApp (A).

## 3. Features worth adding (ranked)

**A. Post the minutes to WhatsApp.** A member already does this by hand every night,
typing up a "Daily Soup Leaderboard". The hand-typed version drops people, cuts lists at
the top 4, mixes up days and is posted about 24 hours late. One button would produce the
same post, complete and correct, in WhatsApp formatting (`*maptap*`, numbered lines, ties
as "=2"), with a link back to the board. It can cover today, the week, or just one game.
This keeps WhatsApp as the place for talk, which the group asked for, and puts the app
behind it. **Highest value, low cost.**

**B. Import a WhatsApp chat export.** The same member's export-and-tally routine, done
properly:
1. Upload the `.txt`.
2. The parser files every result it can read.
3. Each sender maps to a member, and each person claims "which of these is you".

The board starts with 20 days of history, real records and real tenures instead of an
empty sheet. The same parser handles a pasted block of several results. **High value. It
also tests the parser against real data.**

**C. A live reset clock on the agenda.** Countdowns per game, and open items sorted by
the time left before they reset. A reminder goes out an hour before reset for games on
your agenda that you haven't filed (see 1 and 7). This was the app's first stated goal.

**D. Per-game board rules**, one small sheet per game in the chair settings:
- ranked or logged (10)
- metric order and tiebreak (2)
- confidential on or off (6)
- whether late filing counts (9)

**E. Highlights, records and rivalries memos** (13, 14). These give the bored meeting
new kinds of news, beyond just "who won".

**F. Reveal after play** (15). It's cheap because it only uses parsed text.

## 4. For the parser spec

- **Puzzle keys:** a number for most games (`#1235`, `№301`, `No. 96`, `Day #239`,
  `#1,959`). A date for MapTap, Globle, Minute Cryptic, DailyOrbs, the Pyra games and
  Layers, in at least four date formats (`October 28`, `Oct 25, 2026`,
  `Sat, 10/24/2026`, `28 October, 2026`).
- **Noise to strip:**
  - referral params (`?r=`, `?utm_source=`) and angle-bracketed links
  - lines of four spaces
  - zero-width padding inside `[SPOILER]` wrappers
  - comments people add after a result
- **Variants:**
  - a missing header (ANNO `229/500` with no title)
  - a missing percentile (Fermi)
  - a `Globle Stats` prefix
  - Connections' "3x3 Bonus", which is a different puzzle
  - Krillion posted with or without a link
  - mixed units (Noillirk in `m` or `km`)
  - Wiki Game with and without the route in brackets
- **Failures:**
  - Metazooa "I was stumped" with 🔥 0
  - Daily Red "Red won … KO'd"
  - Wordle `X/6`
  - Wiki Game "I gave up"
  - Connections with four mistakes
- **Highlights:**
  - Krillion 🌟
  - Travle `(Perfect)`
  - Minute Cryptic `under/matched/over the community par`
  - Perceptle grade
  - PlayPinDrop "New personal best!" and challenge rounds
- **Test corpus:** the export has about 760 real results for 25 games, which is enough
  to score the parser on recall before launch. The corpus test lives with the export, in
  `research/`.
