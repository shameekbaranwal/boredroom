from datetime import date

from ..core import Game, Metric, Reset
from ..text import emoji_cells, number


class PinDrop(Game):
    id = "pindrop"
    name = "pindrop"
    header = r"^(?:📍\s*)?PlayPinDrop Day #\d+"
    links = ("playpindrop.app",)
    anchor = (241, date(2026, 10, 30))
    reset = Reset()  # the player's own midnight: the chat posts the new date and number from 00:00 IST
    metrics = (Metric("score", "points", "high", max=1000),)
    ranker = ("score",)

    def extract(self, b, r, ctx):
        r.puzzle = int(b.find(r"PlayPinDrop Day #(\d+)")[1])
        score = b.find(r"(\d[\d,]*)\s*/\s*1000")
        r.metric("score", number(score[1]) if score else None)
        markers = b.find(r"^\s*(?:[🎯🟢🟡🟠🔴⚫⚪️]\s*){5}$")  # ⚫ is a round with no points
        if markers:
            r.detail("rounds", "".join(emoji_cells(markers[0])))
        streak = b.find(r"🔥\s*(\d+) day streak")
        if streak:
            r.extras["game_streak"] = int(streak[1])
        if b.find(r"(?i)new personal best"):
            r.highlight("personal best")
        ch = b.find(r"Beat the (\d+) challenge! Rounds: (\d+)-(\d+)")
        if ch:
            r.highlight("challenge won")
            r.extras["challenge"] = {"target": int(ch[1]), "rounds": f"{ch[2]}-{ch[3]}"}
        b.use_links("playpindrop.app")
