from ..core import Game, Metric, Reset
from ..text import month, nearest_year, number


class MapTap(Game):
    id = "maptap"
    name = "maptap"
    header = r"^(?:https?://)?(?:www\.)?maptap\.gg [A-Za-z]+ \d{1,2}$"
    links = ("maptap.gg",)
    key = "date"
    reset = Reset()  # the player's own midnight: the chat posts the new date and number from 00:00 IST
    metrics = (Metric("score", "points", "high", max=1000),)
    ranker = ("score",)

    def extract(self, b, r, ctx):
        m = b.find(r"maptap\.gg ([A-Za-z]+) (\d{1,2})")
        mo, d = month(m[1]), int(m[2])
        r.puzzle = nearest_year(mo, d, self.reset.game_day(ctx.now, ctx.tz)) if mo else None
        rounds = b.find(r"^\s*(\d+)\D+?(\d+)\D+?(\d+)\D+?(\d+)\D+?(\d+)\D*$")
        if rounds:
            r.detail("rounds", [int(x) for x in rounds.groups()])
        total = b.find(r"Final score:\s*([\d,]+)")
        r.metric("score", number(total[1]) if total else None)
