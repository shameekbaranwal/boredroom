import re
from datetime import date

from ..core import Game, Metric


class Perceptle(Game):
    id = "perceptle"
    name = "perceptle"
    header = r"^Perceptle #\d+"
    links = ("perceptle.com",)
    anchor = (105, date(2026, 10, 30))
    metrics = (Metric("score", "points", "high", max=100),)
    ranker = ("score",)

    def extract(self, b, r, ctx):
        m = b.find(r"Perceptle #(\d+)\s*(🃏)?\s*-\s*([A-Z][+-]?)\s*\((\d+)\)")
        r.puzzle = int(m[1])
        r.metric("score", int(m[4]))
        r.detail("grade", m[3], "public")
        if m[2]:
            r.detail("variant", "joker")
        subs = b.find(r"🔢\s*\d+.*\d")
        if subs:
            r.detail("subscores", {k: int(v) for k, v in re.findall(r"(\S+)\s+(\d+)", subs[0])})
        if m[3] == "S":
            r.highlight("grade s")
        b.use_links("perceptle.com")
