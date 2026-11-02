from datetime import date, time

from ..core import Game, Metric, Reset
from ..text import number


class Noillirk(Game):
    id = "noillirk"
    name = "noillirk"
    header = r"^Noillirk daily #\d+"
    links = ("playdaily.org/noillirk",)
    anchor = (34, date(2026, 10, 30))
    reset = Reset("UTC", time(0, 0))  # 05:30 IST, from the chat
    metrics = (Metric("distance", "distance", "high", unit="m"),)  # bigger is better
    ranker = ("distance",)

    def extract(self, b, r, ctx):
        m = b.find(r"Noillirk daily #(\d+)\s*-\s*([\d,.]+)\s*(km|m)\b")
        r.puzzle = int(m[1])
        d = number(m[2])
        r.metric("distance", round(d * 1000) if m[3] == "km" else d)
        theme = b.find(r"^[A-Z][A-Z ,'&-]+$")
        if theme:
            r.detail("theme", theme[0].strip().lower())
        grid = b.rows("🟨⬛⬜🟥🟩🟦🟧🟪")
        r.detail("grid", ["".join(row) for row in grid])
        b.use_links("playdaily.org")
