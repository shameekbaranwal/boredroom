from ..core import Game, Metric
from ..text import duration, make_date, month


class MinuteCryptic(Game):
    id = "cryptic"
    name = "minute cryptic"
    header = r"^Minute Cryptic - \d{1,2} [A-Za-z]+,? \d{4}"
    links = ("minutecryptic.com",)
    key = "date"
    metrics = (
        Metric("hints", "count", "low"),
        Metric("time", "duration", "low", unit="s", optional=True),
    )
    ranker = ("hints", "time")

    def extract(self, b, r, ctx):
        m = b.find(r"Minute Cryptic - (\d{1,2}) ([A-Za-z]+),? (\d{4})")
        r.puzzle = make_date(int(m[3]), month(m[2]), int(m[1]))
        clue = b.find(r"^[\"“](.+)[\"”]\s*\(([\d,\s-]+)\)\s*$")
        if clue:
            r.detail("clue", f"{clue[1]} ({clue[2]})", "spoiler")
        grid = b.rows("⚪🟣🟢🟡🔵🟠🔴⚫")
        r.detail("grid", ["".join(row) for row in grid])
        line = b.find(r"(\d+) hints?")
        r.metric("hints", int(line[1]) if line else None)
        par = b.find(r"(?:(\d+) (under|over)|(matched)) the community par")
        if par:
            if par[2] == "under":
                r.highlight("under par")
                r.extras["par"] = -int(par[1])
            elif par[2] == "over":
                r.extras["par"] = int(par[1])
            else:
                r.highlight("matched par")
                r.extras["par"] = 0
        t = b.find(r"Time: ((?:\d+h\s*)?(?:\d+m\s*)?(?:\d+s)?)\.?")
        if t:
            r.metric("time", duration(t[1]))
        b.use_links("minutecryptic.com")
