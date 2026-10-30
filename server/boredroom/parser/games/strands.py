from datetime import date

from ..core import Game, Metric
from ..text import count


class Strands(Game):
    id = "strands"
    name = "strands"
    header = r"^Strands #\d+"
    links = ("nytimes.com/games/strands",)
    anchor = (971, date(2026, 10, 30))
    metrics = (
        Metric("hints", "count", "low"),
        Metric("spangram", "position", "low"),  # 1 = found it first
    )
    ranker = ("hints", "spangram")

    def extract(self, b, r, ctx):
        r.puzzle = int(b.find(r"Strands #([\d,]+)")[1].replace(",", ""))
        theme = b.find(r"^[“\"](.+)[”\"]$")
        if theme:
            r.detail("theme", theme[1], "detail")  # not a spoiler, by decision
        grid = b.rows("💡🔵🟡")
        flat = [c for row in grid for c in row]
        words = [c for c in flat if c != "💡"]
        r.metric("hints", count(flat, "💡"))
        if "🟡" in words:
            r.metric("spangram", words.index("🟡") + 1)
        r.detail("grid", ["".join(row) for row in grid])
        if r.metrics.get("hints") == 0:
            r.highlight("no hints")
        if r.metrics.get("spangram") == 1:
            r.highlight("spangram first")
