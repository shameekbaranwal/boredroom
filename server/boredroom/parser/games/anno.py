from datetime import date, time

from ..core import Game, Metric, Reset
from ..text import number


class Anno(Game):
    id = "anno"
    name = "anno"
    header = r"^ANNO №\s*\d+"
    links = ("anno-game.netlify.app",)
    # headerless shares start at the rounds line: "97🎯  94🎯  26🤔  0💀  12💀"
    fallback = r"^\s*(?:\d+\S+\s+){4}\d+\S+\s*\n\s*(?:Total:\s*)?\d+/500"
    anchor = (303, date(2026, 10, 30))
    # 10:30 IST is exactly midnight in Chicago (CDT); confirm when US clocks change on 1 Nov
    reset = Reset("America/Chicago", time(0, 0))
    metrics = (Metric("score", "points", "high", max=500),)
    ranker = ("score",)

    def extract(self, b, r, ctx):
        n = b.find(r"ANNO №\s*(\d+)")
        r.puzzle = int(n[1]) if n else None
        rounds = b.find(r"^\s*(\d+)\D+?(\d+)\D+?(\d+)\D+?(\d+)\D+?(\d+)\D*$")
        if rounds:
            r.detail("rounds", [int(x) for x in rounds.groups()])
        total = b.find(r"(?:Total:\s*)?(\d+)/500")
        r.metric("score", number(total[1]) if total else None)
        b.use_links("anno-game.netlify.app")
