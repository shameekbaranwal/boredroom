from datetime import date

from ..core import Game, Metric


class PetGuessr(Game):
    id = "petguessr"
    name = "petguessr"
    header = r"^PetGuessr #\d+"
    links = ("petguessr.com",)
    anchor = (109, date(2026, 10, 30))
    metrics = (Metric("correct", "points", "high", max=10),)
    ranker = ("correct",)

    def extract(self, b, r, ctx):
        m = b.find(r"PetGuessr #(\d+)\s*[—-]\s*(\d+)/10")
        r.puzzle = int(m[1])
        r.metric("correct", int(m[2]))
        grid = b.rows("🐱🐶❌")
        r.detail("grid", ["".join(row) for row in grid])
        b.use_links("petguessr.com")
