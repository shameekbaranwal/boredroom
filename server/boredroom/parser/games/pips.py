from datetime import date

from ..core import Game, Metric
from ..text import duration

LEVELS = {"easy": 1, "medium": 2, "hard": 3}


class Pips(Game):
    """NYT Pips. Each day has three puzzles (easy, medium, hard) under one number;
    a harder puzzle ranks above an easier one, then faster wins."""
    id = "pips"
    name = "pips"
    header = r"^Pips #\d+ (?:Easy|Medium|Hard)\b"
    links = ("nytimes.com/games/pips",)
    key = "number"
    anchor = (421, date(2026, 10, 13))  # one sample, posted from Singapore
    metrics = (
        Metric("level", "grade", "high", max=3),
        Metric("time", "duration", "low", unit="s"),
    )
    ranker = ("level", "time")

    def extract(self, b, r, ctx):
        m = b.find(r"Pips #(\d+) (Easy|Medium|Hard)")
        r.puzzle = int(m[1])
        r.metric("level", LEVELS[m[2].lower()])
        r.detail("level", m[2].lower(), "public")
        t = b.find(r"^\s*(\d+:\d+(?::\d+)?)\s*(\S*)\s*$")
        if t:
            r.metric("time", duration(t[1]))
            if t[2] == "🍪":
                r.highlight("no mistakes")  # assumed: 🍪 = solved without hints
        b.use_links("nytimes.com")
