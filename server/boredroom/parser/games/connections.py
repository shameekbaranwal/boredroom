from datetime import date

from ..core import Game, Metric
from ..text import emoji_cells


class Connections(Game):
    id = "connections"
    name = "connections"
    header = r"^Connections\s*\n\s*Puzzle #\d+"
    links = ("nytimes.com/games/connections",)
    anchor = (1237, date(2026, 10, 30))
    metrics = (Metric("mistakes", "count", "low", max=4),)
    glossary = {"purple first": "the hardest group first"}
    ranker = ("mistakes",)

    COLOURS = "🟨🟩🟦🟪"

    def extract(self, b, r, ctx):
        b.find(r"^Connections\s*$")
        r.puzzle = int(b.find(r"Puzzle #([\d,]+)")[1].replace(",", ""))
        grid = b.rows(self.COLOURS, min_len=4)
        solved = [row for row in grid if len(set(row)) == 1]
        mistakes = len(grid) - len(solved)
        r.metric("mistakes", mistakes)
        r.detail("grid", ["".join(row) for row in grid])
        if len(solved) < 4:
            r.outcome = "failed"
        elif mistakes == 0:
            r.highlight("flawless")
            if solved[0][0] == "🟪":
                r.highlight("purple first")


class ConnectionsBonus(Game):
    """The 3x3 bonus puzzle: dropped by decision (PARSER.md part 6, choice 11)."""
    id = "connections-bonus"
    name = "connections bonus"
    header = r"^Connections 3x3"
    ignore = True
