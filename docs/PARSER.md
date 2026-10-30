# Parser spec (draft 2, 2026-10-30)

The parser turns a pasted share text into a filed result. The same parser runs the paste
box and the internal chat-export import. Everything below is grounded in the soup export
(`research/soup_export.txt`): **about 780 results across 24 games** from 11 members.

Part 6 records the choices made on draft 1. Only DailyOrbs scoring is still open.

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
   rejected. Re-filing the same (member, game, puzzle) goes through the merge below.

**Repeat pastes merge.** When a member pastes a puzzle they've already filed, `merge()`
compares the two:

- **enrich:** the same play with more detail. It merges silently: new fields such as the
  Wiki route are added, missing metrics are filled in, and the score the board already
  saw stays. The richer text is what gets forwarded from then on.
- **duplicate:** nothing new, so it's ignored.
- **conflict:** a different result (a re-do or a re-play). This asks "replace?", and a
  replacement is stamped "amended".

"Same play" means the same puzzle and outcome, with every metric both pastes have
agreeing within the game's `tolerance`. The Wiki Game allows 10 s, because the route
share is copied a few seconds after the plain one; every other game needs exact scores.
In the export, 25 Wiki repeats merge (+route) and 5 are real re-dos (4 wiki, 1
krillion). Once merged, the route is a spoiler field like any other, so other members
see it after filing that puzzle themselves.

Text that matches no game goes to the unknown-game flow (part 6, choice 6): a form
pre-filled from the paste, and a request to add a parser for the game.

**Confidence:** every result is `exact` (header and body parsed), `inferred` (body parsed,
game confirmed by another signal such as the link) or `partial` (known game, but a metric
couldn't be read). The preview says it quietly ("read as anno"). A `partial` result opens
as a form with the parsed values filled in, so the member supplies what's missing.

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
confidence  exact | inferred | partial
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
A metric that only one of the two results has is skipped for that pair (Minute Cryptic
time).

**Visibility of fields**: three levels, from the decisions:

- **public:** shown to everyone, including before you file. The score metrics, outcome,
  highlights, and the game's streak.
- **detail:** shown once you've filed this puzzle. Grids, per-round scores, the Strands
  theme, the Wiki start → end pages.
- **spoiler:** a detail that gives away the answer. It's hidden behind a tap even after
  you've filed, and always wrapped when forwarded (choice 9). The Minute Cryptic clue and the
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
  year (choice 5). Stored as an ISO date.
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
| wiki game | 75 | `A ➡️ B ⏰ 02:09 🦶5` (no title) | page pair (choice 4) | steps ↑, time ↑ | "I gave up after 12 steps" | start → end; *route* |
| anno | 74 | `ANNO №284`; sometimes only `229/500` | number | points /500 ↓ | — | 5 round scores |
| fermi | 67 | `Fermi · No. 77` | number | ratio ↑ (1× is perfect) | — | 3 question ratios |
| connections | 53 | `Connections` / `Puzzle #1219` | number | mistakes ↑ | 4 mistakes, <4 groups | grid (solve order) |
| metazooa | 47 | `🐋 Animal #1169 🐉` (random emoji) | number | guesses ↑ (max 20) | "I was stumped" | grid |
| strands | 34 | `Strands #953` | number | hints ↑, spangram position ↑ | — | theme, grid |
| globle | 33 | `🌎 Oct 12, 2026 🌍`, sometimes `Globle Stats` first | date | guesses ↑ | — | grid |
| minute cryptic | 24 | `Minute Cryptic - 12 October, 2026` | date | hints ↑, time ↑ when both have it | — | *clue*, grid, time, par |
| perceptle | 20 | `Perceptle #100 - B (76)`, sometimes `🃏` | number | score /100 ↓ | — | grade, 5 sub-scores |
| travle | 19 | `#travle #1405 +3` | number | over-par ↑ | not seen yet | grid |
| system design daily | 15 | `System Design Daily #1001` | number | correct /5 ↓ (🟩 count) | — | grid |
| daily red | 14 | `Daily Red #2: Beat Red` / `Red won` | number | outcome, left ↓, turns ↑ | "Red won … KO'd" | grid |
| dailyorbs | 5 | `DailyOrbs October 11 2026` | date | played only for now (choice 10) | — | orb row |

↓ = higher is better, ↑ = lower is better.

Notes:
- **Connections:** mistakes = rows that aren't one colour. The `Connections 3x3 Bonus`
  is a different puzzle and is ignored: not a result, not an unknown game.
- **Strands:** 💡 = a hint used, 🟡 = the spangram, 🔵 = a theme word. The theme line is
  not a spoiler, as decided.
- **Fermi:** numbers have thousands separators (`195,288,089×`). The percentile is
  sometimes missing.
- **Anno, headerless:** `229/500` plus five emoji rounds plus the anno link. Accepted as
  `inferred` when the link is present.

### Tier 2

All of these ship in v1.

| game | n | header | key | metrics |
|---|---|---|---|---|
| noillirk | 7 | `Noillirk daily #30 - 6,763m` | number | distance ↓ (bigger is better) |
| pyragrams, pyraphemes, pyrithmetic (three games) | 9 | `Pyragrams: Sat, 10/24/2026 ✅` | date | 🔀 moves ↑, 🕓 time ↑; 🎯 kept as a field until we know what it counts |
| wordle | 3 | `Wordle 1,953 6/6` | number | guesses /6 ↑, X = fail |
| nyt mini | 3 | `I solved the 10/13/2026 New York Times Mini Crossword in 1:32!` | date | time ↑ |
| layers | 3 | `🏆 Layers #347` + `🗓 Oct 25, 2026` | number | guesses /6 ↑ |
| historydle | 2 | `Historydle #1031 - Classic` | number + mode | rows ↑ |
| petguessr | 1 | `PetGuessr #106 — 5/10` | number | correct /10 ↓ |

## 6. Choices (answered 2026-10-30)

1. **Games are defined as hybrids.** Each game is a small Python class with declared
   metadata (name, header pattern, key type, reset, metrics, ranker, field visibility).
   Its `extract()` handles only the text, and a shared library does dates, numbers and
   grids.
2. **Parsing runs on the server only.** A JS port can come later if the preview feels
   slow.
3. **Lenient, with a confidence field.** A recognised body with a missing header is
   accepted as `inferred` when another signal confirms the game. When confidence is too
   low on a known game, the member fills in the missing details (part 1).
4. **The Wiki Game is keyed by its page pair,** mapped to a date from whoever filed it
   first that day. Filing date plus reset is the fallback when the pair is new.
5. **MapTap's year** is the one that puts the date nearest to now, never more than one day
   ahead.
6. **Unknown games** open a form pre-filled from the paste: the name and link from the
   header, and any obvious number as a suggested score the member confirms. Filing it
   counts as played. The same step sends "add this game" to us with the raw text, which
   becomes the queue of parsers to write. Nothing is ranked until a parser exists.
7. **Strands:** hints, then how early the spangram was found.
8. **Minute Cryptic:** hints, then time when both results have it.
9. **Spoilers are always wrapped on forward.** It can become a chair rule later.
10. **DailyOrbs is played only** for now. *Still open:* a proposed ranking, from what
    people say in the chat (the site couldn't be read; low confidence):
    - each colour is a category; a circle (🟠🟢🔵🟣) is an orb won, and a heart in the
      same colour (🧡💚💙💜) is a lost life ("heart = mistake")
    - proposal: most orbs, then fewest hearts. A run with no hearts would be a highlight
    - unknown: what 🏆 means (it sometimes sits mid-row, and appears on runs with lost
      lives), what a loss looks like, and the exact reset (about 2:30 pm IST, from "new
      daily orbs at 2:30pm")
    - to settle it: a screenshot of the how-to-play or end screen. The parser stores
      circle and heart counts from day one, so turning ranking on later needs no re-parse
11. **The Connections 3x3 Bonus is dropped.**
12. **Noillirk:** a bigger distance is better.
13. **The Pyra games are three games** on one site.
14. **All tier-2 games ship in v1.**

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
