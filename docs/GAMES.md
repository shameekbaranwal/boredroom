# Launch games

The 15 games the friend group plays (list from 2026-10-27). This is the input for the
parser spec, which is the first dev step. Raw pages and JS bundles for each site are
saved in `research/games/` (gitignored) for working out share formats later.

**Confidence:** "verified" = seen in a real shared result or the site's own copy.
Everything else comes from third-party write-ups or is unknown, and needs real share
samples (a WhatsApp chat export is the best source).

| # | Game | What you do | Score shape | Puzzle key | Reset | Share format |
|---|------|-------------|-------------|------------|-------|--------------|
| 1 | [ANNO](https://anno-game.netlify.app/) | Guess the year of 5 historical events | points (likely higher = better) | ? | ? | ? |
| 2 | [Connections](https://www.nytimes.com/games/connections) | Sort 16 words into 4 groups | mistakes 0–4 (4 = missed target); order solved | number (`Puzzle #870`) | local midnight | known: header + 4×4 emoji rows |
| 3 | [Fermi](https://fermi.gg/) | 3 estimation questions, one guess each | closeness score per question | ? | ? | ? |
| 4 | [Globle](https://globle-game.com/game) | Find the country using proximity heat | guesses (lower = better) | date | local midnight (third-party) | ? |
| 5 | [Krillion](https://krillion.io/) | 7 prompts; rarer answers score more | points /700, shown as depth (10 m per point) | date | 00:00 UTC (third-party) | ? |
| 6 | [MapTap](https://maptap.gg/) | Tap 5 locations on a globe | 5 scores 0–100, later ones multiplied; total /1000 | **date only** (`June 18`) | ? | verified: `www.maptap.gg June 18` / `100🎯 90🎉 97🔥 85🌟 63🤨` / `Final score: 828` |
| 7 | [Metazooa](https://metazooa.com/) | Find the mystery animal on the tree of life | guesses, max 20 | ? | ? | ? |
| 8 | [Minute Cryptic](https://www.minutecryptic.com/) | Solve one cryptic clue | hints / letter reveals used | date | ? | ? |
| 9 | [PinDrop](https://playpindrop.app/) | Drop pins on 5 real places | distance-based points | ? | ? | ? |
| 10 | [Daily Orbs](https://dailyorbs.com/) | ? | ? | ? | ? | ? |
| 11 | [System Design Daily](https://systemdesigndaily.com/quiz) | Daily system-design quiz | correct answers (likely) | ? | ? | ? |
| 12 | [Daily Red](https://daily-red.com) | One Pokémon battle against Red with a fixed team | win/loss (+ maybe turns or survivors) | ? | ? | "spoiler-free results grid" (site copy) |
| 13 | [Strands](https://www.nytimes.com/games/strands) | Find theme words + spangram in a letter grid | hints used; order found | number (`#612`) | local midnight | known: header + theme + emoji rows |
| 14 | [The Wiki Game Daily](https://www.thewikigamedaily.com/) | Race between Wikipedia pages | clicks (lower = better), maybe time | ? | ? | ? |
| 15 | [Travle](https://travle.earth/) | Chain countries from A to B | guesses over the minimum; per-guess colors | ? | ? | ? |

## What this already tells the parser spec

- **Score shapes vary widely:** guess counts (lower better), mistakes or hints
  (lower better), points with different maximums (higher better), click counts,
  quiz correct-counts, plain win/loss, and multi-part scores (MapTap's five rounds,
  Fermi's three questions). The spec needs a small set of score *types*, not
  per-game code.
- **Puzzle keys differ:** some games share a number (`#870`), some only a date
  (MapTap's `June 18`, with no year), some possibly neither. Turning a date-only key
  into a puzzle needs the game's reset timezone.
- **Emoji are decoration in some games** (MapTap's 🎯🔥🤨 vary) **and data in
  others** (Connections' colored squares). Parsers must say which.
- **Spoiler safety** needs each parser to mark which fields are safe to show before
  you've played (score, mistakes) and which aren't (Strands' theme line, Connections'
  solve order).
- **Two NYT games share one domain**, so detecting the game by URL alone isn't enough.

## Still needed

One or two real shared results per game, ideally from the WhatsApp group (an export
gives dozens per game, including edge cases such as failures, hard modes and
partial pastes), plus reset times for the games marked "?".
