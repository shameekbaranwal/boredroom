from datetime import date

from ..core import Game, Metric, Reset


class TravleChallenge(Game):
    """Travle's weekly challenge: a route with a country to avoid, new every Monday."""
    id = "travle_challenge"
    name = "travle challenge"
    header = r"^#travle_challenge #\d+"
    links = ("travle.earth",)
    play = "https://travle.earth/challenge"
    anchor = (144, date(2026, 11, 2))  # the week of monday 2 november; one paste so far, see DECISIONS
    reset = Reset(weekday=0)
    metrics = (Metric("over", "count", "low"),)  # guesses over the shortest route
    ranker = ("over",)

    def extract(self, b, r, ctx):
        m = b.find(r"#travle_challenge #(\d+) \+(\d+)(?: \((Perfect)\))?(?: \((\d+) hints?\))?")
        if m:
            r.puzzle = int(m[1])
            r.metric("over", int(m[2]))
            if m[3]:
                r.highlight("perfect")
            if m[4]:
                r.extras["hints"] = int(m[4])
        else:  # as travle: a failure has no "+N"
            r.puzzle = int(b.find(r"#travle_challenge #(\d+)")[1])
            r.outcome = "failed"
        grid = b.rows("🟥🟧🟨🟩✅⬛⬜")
        r.detail("grid", ["".join(row) for row in grid])
        b.use_links("travle.earth")
