from ..core import Game, Metric
from ..text import make_date, month


class Globle(Game):
    id = "globle"
    name = "globle"
    header = r"^(?:Globle Stats\s*)?🌎 [A-Za-z]{3} \d{1,2}, \d{4} 🌍"
    links = ("globle-game.com",)
    key = "date"
    metrics = (Metric("guesses", "count", "low"),)
    ranker = ("guesses",)

    def extract(self, b, r, ctx):
        m = b.find(r"🌎 ([A-Za-z]{3}) (\d{1,2}), (\d{4}) 🌍")
        r.puzzle = make_date(int(m[3]), month(m[1]), int(m[2]))
        streak = b.find(r"🔥\s*(\d+)\s*\|")
        if streak:
            r.extras["game_streak"] = int(streak[1])
        grid = b.find_all(r"^[🟥🟧🟨🟩⬜️\s]+(?:=\s*(\d+))?\s*$")
        total = next((int(g[1]) for g in grid if g[1]), None)
        r.metric("guesses", total)
        r.detail("grid", [g[0].split("=")[0].strip() for g in grid])
        if total is not None and total <= 3:
            r.highlight(f"in {total}")
        b.use_links("globle-game.com")
        b.find(r"^#globle$")
