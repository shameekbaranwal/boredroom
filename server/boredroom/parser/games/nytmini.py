from ..core import Game, Metric
from ..text import duration, make_date


class NYTMini(Game):
    id = "mini"
    name = "nyt mini"
    header = r"^I solved the \d{1,2}/\d{1,2}/\d{4} New York Times Mini Crossword"
    links = ("nytimes.com", "nytimes.onelink.me")
    play = "https://www.nytimes.com/crosswords/game/mini"
    key = "date"
    metrics = (Metric("time", "duration", "low", unit="s"),)
    ranker = ("time",)

    def extract(self, b, r, ctx):
        m = b.find(r"I solved the (\d{1,2})/(\d{1,2})/(\d{4}) New York Times Mini Crossword in ([\d:]+)")
        r.puzzle = make_date(int(m[3]), int(m[1]), int(m[2]))
        r.metric("time", duration(m[4]))
        b.use_links("nytimes")
