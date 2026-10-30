from datetime import date

from ..core import Game, Metric


class DailyRed(Game):
    id = "red"
    name = "daily red"
    header = r"^Daily Red #\d+"
    links = ("daily-red.com",)
    anchor = (19, date(2026, 10, 30))
    metrics = (
        Metric("left", "count", "high", max=6, optional=True),  # your team left standing (wins)
        Metric("knocked", "count", "high", max=6, optional=True),  # red's team you KO'd (losses)
        Metric("turns", "count", "low"),
    )
    ranker = ("left", "knocked", "turns")

    def extract(self, b, r, ctx):
        m = b.find(r"Daily Red #(\d+):\s*(Beat Red|Red won)")
        r.puzzle = int(m[1])
        r.outcome = "solved" if m[2] == "Beat Red" else "failed"
        line = b.find(r"(\d)/6 (left|KO'd) · (\d+) turns")
        if line:
            r.metric("left" if line[2] == "left" else "knocked", int(line[1]))
            r.metric("turns", int(line[3]))
            r.detail("team", line.string.split(line[1] + "/6")[0].strip())
            if line[2] == "left" and line[1] == "6":
                r.highlight("flawless")
        streak = b.find(r"Streak (\d+)")
        if streak:
            r.extras["game_streak"] = int(streak[1])
        b.use_links("daily-red.com")
