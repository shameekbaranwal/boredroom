from datetime import date, time

from ..core import Game, Metric, Reset
from ..text import number


class Fermi(Game):
    id = "fermi"
    name = "fermi"
    header = r"^Fermi · No\. ?\d+"
    links = ("fermi.gg",)
    anchor = (96, date(2026, 10, 30))
    reset = Reset("America/New_York", time(0, 0))  # midnight eastern: 09:30 IST in us summer, 10:30 in winter
    # how many times off your guesses were, combined; 1× is perfect
    metrics = (Metric("score", "ratio", "low", unit="×"),)
    ranker = ("score",)

    def extract(self, b, r, ctx):
        r.puzzle = int(b.find(r"Fermi · No\. ?(\d+)")[1])
        qs = b.find_all(r"^\s*0?(\d)\s+([\d,.]+)×\s*$")
        r.detail("questions", [number(m[2]) for m in qs])
        b.find(r"^[─—-]{3,}$")
        s = b.find(r"([\d,.]+)×\s*score(?:\s*·\s*top (\d+)%)?")
        r.metric("score", number(s[1]) if s else None)
        if s and s[2]:
            r.extras["percentile"] = int(s[2])
        if qs and all(number(m[2]) == 1 for m in qs):
            r.highlight("perfect")
        b.use_links("fermi.gg")
