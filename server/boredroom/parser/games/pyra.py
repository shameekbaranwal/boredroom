"""Three games on one site (PARSER.md part 6, choice 13)."""
from ..core import Game, Metric
from ..text import duration, make_date


class _Pyra(Game):
    links = ("pyralinks.com",)
    key = "date"
    metrics = (
        Metric("moves", "count", "low"),
        Metric("time", "duration", "low", unit="s"),
    )
    ranker = ("moves", "time")

    def extract(self, b, r, ctx):
        m = b.find(rf"{self.name.capitalize()}: \w{{3}}, (\d{{1,2}})/(\d{{1,2}})/(\d{{4}})\s*(✅|❌)?")
        r.puzzle = make_date(int(m[3]), int(m[1]), int(m[2]))
        if m[4] == "❌":
            r.outcome = "failed"
        s = b.find(r"🎯\s*(\d+)\s*🔀\s*(\d+)\s*🕓\s*([\d:]+)")
        if s:
            r.detail("🎯", int(s[1]))  # meaning unknown; kept until we know
            r.metric("moves", int(s[2]))
            r.metric("time", duration(s[3]))
        grid = b.find_all(r"^\s*[▪️🟩🟪🟨🟥⬛⬜\s]+$")
        r.detail("grid", [g[0] for g in grid])
        b.use_links("pyralinks.com")


class Pyragrams(_Pyra):
    id = "pyragrams"
    name = "pyragrams"
    header = r"^Pyragrams: \w{3}, \d"


class Pyraphemes(_Pyra):
    id = "pyraphemes"
    name = "pyraphemes"
    header = r"^Pyraphemes: \w{3}, \d"


class Pyrithmetic(_Pyra):
    id = "pyrithmetic"
    name = "pyrithmetic"
    header = r"^Pyrithmetic: \w{3}, \d"
