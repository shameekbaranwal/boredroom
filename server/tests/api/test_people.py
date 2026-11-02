"""A member's page: what they play on the board, and how it's going."""
from datetime import timedelta

from .test_memos import OCT30, board, clock, file, krillion, wordle  # noqa: F401 (clock is a fixture)


def test_a_members_activity(db, seat):
    (judy, trent), people, b = board(db, seat, "judy", "trent")
    for n in range(4):  # judy files krillion four days running, and beats trent on the last two
        d = OCT30 - timedelta(days=3 - n)
        file(db, people["judy"], krillion(d, 400 + n), d)
        if n >= 2:
            file(db, people["trent"], krillion(d, 100), d)
    file(db, people["judy"], wordle(OCT30, 3), OCT30)

    page = trent.get("/boards/soup/members/judy").json
    assert (page["nickname"], page["me"], page["present"], page["wins"]) == ("judy", False, 4, 2)
    k = next(g for g in page["games"] if g["game"] == "krillion")
    assert (k["results"], k["tenure"], k["longest"], k["wins"], k["best"]) == (4, 4, 4, 2, {"score": 403})
    assert page["strip"][-4:] == [1, 1, 1, 2]  # today she filed krillion and wordle
    top = page["recent"][0]
    assert top["day"] == "2026-10-30"
    assert [(r["game"], r["place"], r["of"]) for r in page["recent"] if r["game"] == "krillion"][:2] == [("krillion", "1", 2)] * 2
    assert "raw" not in top and "fields" not in top  # the score only: details stay in the minutes
    assert trent.get("/boards/soup/members/nobody").status_code == 404
