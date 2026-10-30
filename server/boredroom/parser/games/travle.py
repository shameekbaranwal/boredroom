from datetime import date

from ..core import Game, Metric


class Travle(Game):
    id = "travle"
    name = "travle"
    header = r"^#travle #\d+"
    links = ("travle.earth",)
    anchor = (1416, date(2026, 10, 30))
    metrics = (Metric("over", "count", "low"),)  # guesses over the shortest route
    ranker = ("over",)

    def extract(self, b, r, ctx):
        m = b.find(r"#travle #(\d+) \+(\d+)(?: \((Perfect)\))?(?: \((\d+) hints?\))?")
        if m:
            r.puzzle = int(m[1])
            r.metric("over", int(m[2]))
            if m[3]:
                r.highlight("perfect")
            if m[4]:
                r.extras["hints"] = int(m[4])
        else:  # failures don't carry "+N"; seen formats needed
            r.puzzle = int(b.find(r"#travle #(\d+)")[1])
            r.outcome = "failed"
        grid = b.rows("🟥🟧🟨🟩✅⬛⬜")
        r.detail("grid", ["".join(row) for row in grid])
        b.use_links("travle.earth")
