from ..core import Game, Metric
from ..text import number


class KrillionGeo(Game):
    """Krillion's geography pack: 7 questions, rarer answers score more. Not a daily: the
    pack's 203 numbered games are played in any order, and a shared link opens the same one.
    So a result belongs to the day it's filed (your own midnight), one a day; the game's
    number is kept, so the board can see who played which."""
    id = "krillion_geo"
    name = "krillion geo"
    header = r"^KRILLION Around the World #\d+"
    links = ("krillion.to",)
    play = "https://krillion.to/en/geography"
    key = "date"
    metrics = (Metric("score", "points", "high", max=700),)
    ranker = ("score",)
    glossary = {"krillion": "an answer almost nobody gives, worth the most"}

    # one per question, most common -> rarest; × is a miss
    TIERS = "·◇≈◆✦◉×"

    def extract(self, b, r, ctx):
        r.puzzle = ctx.today
        r.detail("game", int(b.find(r"Around the World #(\d+)")[1]))
        score = b.find(r"^\s*(\d[\d,]*)\s*/\s*700\b")
        r.metric("score", number(score[1]) if score else None)
        tiers = b.find(r"^\s*([·◇≈◆✦◉×](?:\s*[·◇≈◆✦◉×]){2,})\s*$")
        if tiers:
            r.detail("answers", tiers[1].replace(" ", ""))
            if "◉" in tiers[1]:
                r.highlight("krillion")
        b.find(r"^How deep will your knowledge take you\?")
        b.use_links("krillion.to")
