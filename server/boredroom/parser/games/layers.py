from datetime import date

from ..core import Game, Metric


class Layers(Game):
    id = "layers"
    name = "layers"
    header = r"^(?:\S+\s*)?Layers #\d+"
    links = ("hiddenlayerlabs.com/layers",)
    play = "https://hiddenlayerlabs.com/play/"
    anchor = (352, date(2026, 10, 30))
    metrics = (Metric("guesses", "count", "low", max=6),)
    ranker = ("guesses",)

    def extract(self, b, r, ctx):
        r.puzzle = int(b.find(r"Layers #(\d+)")[1])
        b.find(r"🗓")
        res = b.find(r"(\d)/6\s*(✅|❌)")
        if res:
            r.metric("guesses", int(res[1]))
            if res[2] == "❌":
                r.outcome = "failed"
        grid = b.find_all(r"^\s*[🟧🟪🟩🟦🟨⬛⬜\s]+$")
        r.detail("grid", [g[0] for g in grid])
        extras = b.find(r"📝.*")
        if extras:
            r.detail("summary", extras[0].strip())
        b.find(r"(?i)play today's layers")
        b.use_links("hiddenlayerlabs.com")
