from datetime import date, time

from ..core import Game, Metric, Reset
from ..text import count, number


class Krillion(Game):
    id = "krillion"
    name = "krillion"
    header = r"^Krillion #\d+"
    links = ("krillion.io",)
    anchor = (107, date(2026, 10, 30))
    # 9:30 IST is exactly midnight in New York (EDT); confirm when US clocks change on 1 Nov
    reset = Reset("America/New_York", time(0, 0))
    metrics = (Metric("score", "points", "high", max=700),)
    ranker = ("score",)

    RARITY = "🫧🐟🏮🦑🌟"  # most common -> rarest; 🌟 is a krill

    def extract(self, b, r, ctx):
        r.puzzle = int(b.find(r"Krillion #(\d+)")[1])
        score = b.find(r"^\s*(\d[\d,]*)\s*$")
        r.metric("score", number(score[1]) if score else None)
        grid = b.rows(self.RARITY, min_len=3)
        if grid:
            r.detail("answers", "".join(grid[0]))
            krills = count(grid, "🌟")
            if krills:
                r.highlight("krill")
                r.extras["krills"] = krills
        b.use_links("krillion.io")
