from datetime import date

from ..core import Game, Metric


class Metazooa(Game):
    id = "metazooa"
    name = "metazooa"
    header = r"^\S+ Animal #\d+(?: \S+)?$"  # the emoji around it change daily
    links = ("metazooa.com",)
    anchor = (1187, date(2026, 10, 30))
    metrics = (Metric("guesses", "count", "low", max=20),)
    ranker = ("guesses",)

    def extract(self, b, r, ctx):
        r.puzzle = int(b.find(r"Animal #(\d+)")[1])
        won = b.find(r"(?i)figured it out in (\d+) guess")
        if won:
            r.metric("guesses", int(won[1]))
            if int(won[1]) <= 3:
                r.highlight(f"in {won[1]}")
        elif b.find(r"(?i)I was stumped"):
            r.outcome = "failed"
        grid = b.rows("🟥🟧🟨🟩", min_len=1)
        r.detail("grid", ["".join(row) for row in grid])
        streak = b.find(r"🔥\s*(\d+)\s*\|")
        if streak:
            r.extras["game_streak"] = int(streak[1])
        b.use_links("metazooa.com")
        b.find(r"^#metazooa$")
