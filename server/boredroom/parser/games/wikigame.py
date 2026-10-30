import re

from ..core import Game, Metric
from ..text import duration


class WikiGame(Game):
    id = "wiki"
    name = "wiki game"
    header = r"^.+? ➡️ .+? ⏰ \d+:\d+(?::\d+)? 🦶\s*\d+"
    links = ("thewikigamedaily.com",)
    key = "pair"
    metrics = (
        Metric("steps", "count", "low"),
        Metric("time", "duration", "low", unit="s"),
    )
    ranker = ("steps", "time")

    def extract(self, b, r, ctx):
        m = b.find(r"^(.+?) ➡️ (.+?) ⏰ (\d+:\d+(?::\d+)?) 🦶\s*(\d+)(?:\s*\((.*)\))?")
        start, end = m[1].strip(), m[2].strip()
        # the page pair is the puzzle; the app maps it to a date (choice 4)
        r.puzzle = f"{start} → {end}".lower()
        r.metric("steps", int(m[4]))
        r.metric("time", duration(m[3]))
        r.detail("pages", f"{start} → {end}")
        if m[5]:
            r.detail("route", [p.strip() for p in m[5].split("➡️")], "spoiler")
        b.use_links("thewikigamedaily.com")
        gave_up = b.find(r"(?i)gave up(?: after (\d+) steps?)?")
        if gave_up:
            r.outcome = "failed"
