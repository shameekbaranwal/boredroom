from datetime import time

from ..core import Game, Metric, Reset
from ..text import count, emoji_cells, make_date, month


class DailyOrbs(Game):
    """Played only for now (PARSER.md part 6, choice 10). Orbs and lost lives are stored
    so a ranking can be switched on later without re-parsing."""
    id = "orbs"
    name = "dailyorbs"
    header = r"^DailyOrbs [A-Za-z]+ \d{1,2},? \d{4}"
    links = ("dailyorbs.com",)
    key = "date"
    reset = Reset("UTC", time(9, 0))  # about 2:30 pm IST, from the chat
    metrics = (
        Metric("orbs", "count", "high", optional=True),
        Metric("lives_lost", "count", "low", optional=True),
    )
    ranker = ()

    def extract(self, b, r, ctx):
        m = b.find(r"DailyOrbs ([A-Za-z]+) (\d{1,2}),? (\d{4})")
        r.puzzle = make_date(int(m[3]), month(m[1]), int(m[2]))
        r.outcome = "played"
        b.use_links("dailyorbs.com")
        row = b.find(r"^[🟠🟢🔵🟣🟡🔴🧡💚💙💜💛❤🏆\s]+$")
        if row:
            cells = emoji_cells(row[0])
            r.metric("orbs", count(cells, "🟠🟢🔵🟣🟡🔴"))
            r.metric("lives_lost", count(cells, "🧡💚💙💜💛❤"))
            r.detail("orbs", "".join(cells))
