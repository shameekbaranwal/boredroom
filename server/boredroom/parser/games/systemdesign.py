from datetime import date, time

from ..core import Game, Metric, Reset
from ..text import count


class SystemDesignDaily(Game):
    id = "sdd"
    name = "system design daily"
    header = r"^System Design Daily #\d+"
    links = ("systemdesigndaily.com",)
    play = "https://systemdesigndaily.com/quiz"
    anchor = (1018, date(2026, 10, 30))
    # 12:30 IST is exactly midnight in Los Angeles (PDT); confirm when US clocks change on 1 Nov
    reset = Reset("America/Los_Angeles", time(0, 0))
    metrics = (Metric("correct", "points", "high", max=5),)
    ranker = ("correct",)

    def extract(self, b, r, ctx):
        r.puzzle = int(b.find(r"System Design Daily #(\d+)")[1])
        grid = b.rows("🟩🟥🟨")
        r.metric("correct", count(grid, "🟩"))
        r.detail("grid", ["".join(row) for row in grid])
        if grid and count(grid, "🟥🟨") == 0:
            r.highlight("perfect")
        b.use_links("systemdesigndaily.com")
