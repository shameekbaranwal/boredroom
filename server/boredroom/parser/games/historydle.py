from datetime import date

from ..core import Game, Metric


class Historydle(Game):
    id = "historydle"
    name = "historydle"
    header = r"^Historydle #\d+"
    links = ("historydle.com",)
    anchor = (1033, date(2026, 10, 30))
    metrics = (Metric("guesses", "count", "low"),)
    ranker = ("guesses",)

    def extract(self, b, r, ctx):
        m = b.find(r"Historydle #(\d+)(?:\s*-\s*(\w+))?")
        r.puzzle = int(m[1])
        if m[2]:
            r.detail("mode", m[2].lower(), "public")
        grid = b.rows("⬛⬜🟩🟨🟥", min_len=5)
        r.detail("grid", ["".join(row) for row in grid])
        if grid and all(c == "🟩" for c in grid[-1]):
            r.metric("guesses", len(grid))
        else:
            r.outcome = "failed"
        b.use_links("historydle.com")
