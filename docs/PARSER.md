# Parser spec (draft 1, 2026-10-30)

The parser turns a pasted share text into a filed result. The same parser runs the paste
box and the internal chat-export import. Everything below is grounded in the soup export
(`research/soup_export.txt`): **about 780 results across 24 games** from 11 members.

Part 6 lists the open choices, numbered so they can be answered by number. Each one says
what I'd pick.

## 1. What the parser does

The paste becomes zero or more results:

```
paste ──► normalise ──► split ──► detect game ──► extract ──► key the puzzle ──► check ──► results
```

1. **Normalise** (the same for every game):
   - strip zero-width and bidi characters (U+200B–U+200F, U+2060, U+FEFF). One spoiler
     wrapper carried 4,000 of them
   - strip WhatsApp's `<This message was edited>` and the angle brackets around links
   - drop tracking parameters (`?r=`, `?utm_source=`, `?si=`)
   - unify line endings and drop lines that are only spaces (Metazooa adds one)
   - keep the original text untouched next to the normalised one, for "send to soup"
2. **Split:** one paste can hold several results. Every game defines a *start marker*
   (its header line). Text from one marker to the next belongs to that game. Text before
   the first marker or after a result's last recognised line becomes a **comment**
   ("worst one yet", "ignore the time"). It is kept and shown as a note, never parsed.
3. **Detect:** a game is recognised by its header first, its link second. Two NYT games
   share a domain, and some pastes have no link, so the header is what counts.
4. **Extract:** each game's extractor returns its metrics, outcome, fields and highlights
   (part 2). A recognised header whose body doesn't parse is a **broken result**, not an
   unknown game: "this looks like krillion but the score is missing".
5. **Key:** work out which puzzle it is (part 3).
6. **Check:** values must be in range (anno ≤ 500, maptap ≤ 1000, wordle ≤ 6 guesses).
   A filing for a puzzle more than one day ahead of that game's current puzzle is
   rejected. Re-filing the same (member, game, puzzle) asks to replace, as decided.

Text that matches no game goes to the unknown-game flow in the UX ("add *perceptle* to
the agenda?").

## 2. The result record

```
game        "krillion"
puzzle      "#98"            number or ISO date, see part 3
outcome     solved | failed | played
metrics     {score: 310}     named, typed values, see the table below
fields      [{name, value, visibility}]   everything else worth showing
highlights  ["krill"]
extras      {game_streak: 20}
comment     "low score but i got a krill, so"
raw         the original paste
parser      "krillion@1"     extractor version, so old results can be re-parsed
```

**Metric types**: a small fixed set, so rankers stay generic.

| type | example | stored as |
|---|---|---|
| points | anno 233/500, maptap 935 | integer, with max |
| count | guesses, mistakes, hints, steps | integer, with max where the game has one |
| ratio | fermi 10.8× | decimal |
| duration | wiki 02:09, mini 1:32 | seconds |
| distance | noillirk 6,763 m | metres |
| grade | perceptle B | ordered label |
| position | strands spangram found 2nd | integer |

**Outcome:** `failed` is first-class. 25 of the 53 Connections results in the export are
four mistakes without a solve. Wordle `X/6`, Metazooa "stumped", Daily Red "Red won" and
Wiki "I gave up" fail too. A failure always ranks below every solve and still counts as
played. `played` is for games with no score (DailyOrbs).

**Rankers** sit in the game definition, not the extractor: an ordered list of
`(metric, direction)`, with outcome always first. For example, the Wiki Game is
`[outcome, steps asc, time asc]`, and the chair can reorder it. Equal on every key = tie.

**Visibility of fields**: three levels, from the decisions:

- **public:** shown to everyone, including before you file. The score metrics, outcome,
  highlights, and the game's streak.
- **detail:** shown once you've filed this puzzle. Grids, per-round scores, the Strands
  theme, the Wiki start → end pages.
- **spoiler:** a detail that gives away the answer. It's hidden behind a tap even after
  you've filed, and wrapped when forwarded (option 9). The Minute Cryptic clue and the
  Wiki route.

## 3. Puzzle keys and "today"

Every result gets a puzzle key. A game's "today" for a member is the puzzle key that is
current for them now.

- **Number keys** (most games): `#1219`, `№284`, `No. 77`, `Day #223`, `#1,953`.
  Commas are stripped. The game definition holds one anchor (puzzle N went live at date D)
  plus the reset rule, so `current(game, now, member tz)` is arithmetic.
- **Date keys** (MapTap, Globle, Minute Cryptic, DailyOrbs, the Pyra games, the Mini).
  There are six formats in the export: `October 12`, `Oct 12, 2026`, `12 October, 2026`,
  `Sat, 10/24/2026`, `10/13/2026`, and the ISO date in the DailyOrbs link. MapTap has no
  year (option 5). Stored as an ISO date.
- **Reset rules** per game, either a fixed UTC time (one puzzle for the world) or the
  player's local midnight. Observed in IST:
  - krillion: 9:30 (04:00 UTC)
  - anno: 10:30 (05:00 UTC)
  - maptap, pindrop and fermi: 5:30 (00:00 UTC)
  - dailyorbs: 2:30 pm (09:00 UTC)
  - NYT games and most others: local midnight

  The local-midnight ones matter for the Singapore member: their today flips 2.5 h
  earlier.
- **Filed late** = the puzzle key is older than the member's current puzzle when filed.

## 4. Highlights and extras

Highlights are flags the share text itself gives. They feed the memos.

| game | highlight | from |
|---|---|---|
| krillion | krill | 🌟 in the grid (count them: "2 krills") |
| travle | perfect | `(Perfect)` |
| minute cryptic | under par / matched par | `– 1 under the community par` |
| pindrop | personal best | `New personal best!` |
| pindrop | challenge won | `🏆 Beat the 691 challenge! Rounds: 4-0.` |
| connections | flawless | 0 mistakes (derived) |
| strands | no hints | no 💡 (derived) |
| wordle, metazooa, globle | in N | a low guess count (derived, threshold per game) |
| perceptle | grade S | grade (none seen yet) |

**Extras** are kept but not ranked: game streak (`🔥 20 day streak`, `🔥 13 |`), fermi
percentile (`top 54%`), solver counts. The game's streak shows beside our tenure without
merging the two, as decided.

## 5. Games

Counts are results in the export. **Tier 1** are the 15 launch games, plus Perceptle,
which was played enough to join them. **Tier 2** were seen only a few times.

### Tier 1

| game | n | header (start marker) | key | metrics → default ranker | fails | detail / *spoiler* |
|---|---|---|---|---|---|---|
| maptap | 98 | `www.maptap.gg October 12` | date, no year | points /1000 ↓ | — | 5 round scores |
| krillion | 94 | `Krillion #89 🦐` | number | points /700 ↓ | — | rarity grid (🫧🐟🏮🦑🌟) |
| pindrop | 79 | `📍 PlayPinDrop Day #223` | number | points /1000 ↓ | — | 5 round markers |
| wiki game | 75 | `A ➡️ B ⏰ 02:09 🦶5` (no title) | none in text (option 4) | steps ↑, time ↑ | "I gave up after 12 steps" | start → end; *route* |
| anno | 74 | `ANNO №284`; sometimes only `229/500` | number | points /500 ↓ | — | 5 round scores |
| fermi | 67 | `Fermi · No. 77` | number | ratio ↑ (1× is perfect) | — | 3 question ratios |
| connections | 53 | `Connections` / `Puzzle #1219` | number | mistakes ↑ | 4 mistakes, <4 groups | grid (solve order) |
| metazooa | 47 | `🐋 Animal #1169 🐉` (random emoji) | number | guesses ↑ (max 20) | "I was stumped" | grid |
| strands | 34 | `Strands #953` | number | hints ↑, spangram position ↑ (option 7) | — | theme, grid |
| globle | 33 | `🌎 Oct 12, 2026 🌍`, sometimes `Globle Stats` first | date | guesses ↑ | — | grid |
| minute cryptic | 24 | `Minute Cryptic - 12 October, 2026` | date | hints ↑ (option 8) | — | *clue*, grid, time, par |
| perceptle | 20 | `Perceptle #100 - B (76)`, sometimes `🃏` | number | score /100 ↓ | — | grade, 5 sub-scores |
| travle | 19 | `#travle #1405 +3` | number | over-par ↑ | not seen yet | grid |
| system design daily | 15 | `System Design Daily #1001` | number | correct /5 ↓ (🟩 count) | — | grid |
| daily red | 14 | `Daily Red #2: Beat Red` / `Red won` | number | outcome, left ↓, turns ↑ | "Red won … KO'd" | grid |
| dailyorbs | 5 | `DailyOrbs October 11 2026` | date | none, played only (option 10) | — | orb row |

↓ = higher is better, ↑ = lower is better.

Notes:
- **Connections:** mistakes = rows that aren't one colour. The `Connections 3x3 Bonus`
  is a different puzzle (option 11).
- **Strands:** 💡 = a hint used, 🟡 = the spangram, 🔵 = a theme word. The theme line is
  not a spoiler, as decided.
- **Fermi:** numbers have thousands separators (`195,288,089×`). The percentile is
  sometimes missing.
- **Anno, headerless:** `229/500` plus five emoji rounds plus the anno link. Accept it
  when the link is present (option 3).

### Tier 2

| game | n | header | key | metrics |
|---|---|---|---|---|
| noillirk | 7 | `Noillirk daily #30 - 6,763m` | number | distance; direction unknown (option 12) |
| pyragrams / pyraphemes / pyrithmetic | 9 | `Pyragrams: Sat, 10/24/2026 ✅` | date | 🎯 ?, 🔀 moves, 🕓 time (option 13) |
| wordle | 3 | `Wordle 1,953 6/6` | number | guesses /6 ↑, X = fail |
| nyt mini | 3 | `I solved the 10/13/2026 New York Times Mini Crossword in 1:32!` | date | time ↑ |
| layers | 3 | `🏆 Layers #347` + `🗓 Oct 25, 2026` | number | guesses /6 ↑ |
| historydle | 2 | `Historydle #1031 - Classic` | number + mode | rows ↑ |
| petguessr | 1 | `PetGuessr #106 — 5/10` | number | correct /10 ↓ |

## 6. Open choices

1. **How games are defined.**
   - (a) Pure data: YAML with regexes per field. Easy to add games, but it falls apart on
     grids and derived values.
   - (b) One Python module per game.
   - (c) **Hybrid:** each game is a small Python class with declared metadata (name,
     header pattern, key type, reset, metrics, ranker, field visibility). Its
     `extract()` handles only the text, and a shared library does dates, numbers and
     grids.

   I'd pick (c). It keeps games as data where that's easy, and in code where they aren't.

2. **Where parsing runs.**
   - (a) **Server only:** the paste goes up and the preview comes back, about 100 ms.
   - (b) Also in the browser for instant preview, which means writing it twice.

   I'd pick (a); a JS port can come later if the preview feels slow.

3. **How strict.** Accept a paste with a recognised body but a missing header (the
   headerless anno) when another signal confirms the game, like the link? I'd say yes,
   and mark it `confidence: inferred` so the preview says "read as anno".

4. **Wiki Game puzzle key.** The text has no number or date, only the start → end pages.
   - (a) **Key by the page pair**, mapped to a date from whoever filed it first that
     day. Same pair, same puzzle.
   - (b) Key by filing date and reset only.

   I'd pick (a), with (b) as the fallback when the pair is new. It also catches someone
   pasting yesterday's route.

5. **MapTap has no year.** Pick the year that puts the date nearest to now (never more
   than one day ahead). That's safe for a daily game; a year-old MapTap would be misread,
   which is fine.

6. **Unknown games.**
   - (a) Store the raw text, count it as played, and give it no score until a parser
     exists.
   - (b) Also guess a score with a generic "first N/M or number" rule.

   I'd pick (a). Wrong guesses would put wrong numbers on the board. The unknown pastes
   also become the queue of parsers to write.

7. **Strands ranking.**
   - (a) Hints only.
   - (b) **Hints, then how early the spangram was found** (what the UX uses).
   - (c) Logged, not ranked.

   I'd pick (b). The chat treats Strands as "not much competitive", so (c) as the chair's
   default is also reasonable.

8. **Minute Cryptic ranking.** Hints, then time? Time is missing from some shares, as in
   Mallory's. I'd rank by hints only, with par as a highlight and time as a tiebreak only
   when both have it.

9. **Spoiler wrapping on forward.** People already hand-wrap Wiki results as
   `[WIKI SPOILER]` plus invisible padding, so WhatsApp folds them under "read more".
   "Send to soup" could do that automatically for any result with a spoiler field.
   Options: (a) **always**, (b) a per-board rule for the chair, (c) never. I'd pick (a)
   now, with (b) as a later chair rule.

10. **Games with no score** (DailyOrbs). Is "played" enough, or should we count something
    from the grid (orbs, the 🏆)? I'd keep it at played until someone in soup says what
    a good orbs result is.

11. **Connections 3x3 Bonus.** Treat it as its own game ("connections bonus"), or drop it?
    I'd make it its own tier-2 game; it showed up once.

12. **Noillirk direction.** Is a bigger distance better or worse? The one "what" after
    45 m suggests 45 m is bad, so bigger is better. That needs a soup member to confirm.

13. **Pyra games.** Are they three games or one with three modes? What does 🎯 count? I'd
    make them three games, ranked by 🔀 moves, then 🕓 time, until we know.

14. **Which tier-2 games ship in v1?** I'd ship all of them. Each is about 20 lines on top
    of the shared library, and the export has fixtures for them. Anything new goes
    through the unknown-game flow.

## 7. Testing

- **Corpus:** a script splits the export into messages and writes one fixture per
  result: raw text, sender, timestamp. It lives in `research/` (gitignored, since it's
  private chat). A few hand-picked, anonymised samples per game get committed as unit
  fixtures.
- **Labels:** expected records for the corpus are generated once by the first parser,
  then reviewed by hand game by game, and become golden files. After that, any parser
  change shows up as a diff.
- **Targets before launch:** ≥ 98% of tier-1 results parse with no warning. Zero chat
  messages that aren't results get read as one (precision matters more; a false result
  on the board is worse than a missed one). Every failure shape in part 5 has a test.
- **Import gotchas:** the export folds system lines ("changed the group description")
  into the previous message's body in 19 places. Results are often posted alone, so an
  imported result's comment is the rest of that message, and replies are never merged.
  peggy's hand-typed "Daily Soup Leaderboard" posts must be skipped, not parsed.
