from datetime import date

from ..core import Game, Metric


class Wordle(Game):
    id = "wordle"
    name = "wordle"
    header = r"^Wordle [\d,]+ [X1-6]/6"
    links = ("nytimes.com/games/wordle",)
    anchor = (1959, date(2026, 10, 30))
    metrics = (Metric("guesses", "count", "low", max=6),)
    ranker = ("guesses",)

    def extract(self, b, r, ctx):
        m = b.find(r"Wordle ([\d,]+) ([X1-6])/6(\*)?")
        r.puzzle = int(m[1].replace(",", ""))
        if m[2] == "X":
            r.outcome = "failed"
        else:
            r.metric("guesses", int(m[2]))
            if int(m[2]) <= 2:
                r.highlight(f"in {m[2]}")
        if m[3]:
            r.detail("mode", "hard", "public")
        grid = b.rows("⬛⬜🟨🟩🟧🟦")
        r.detail("grid", ["".join(row) for row in grid])
