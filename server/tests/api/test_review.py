from boredroom import reads
from boredroom.models import Board, Person

from .conftest import NOW

KRILLION = "Krillion #{n} 🦐\n{score}\n\n🐟🐟🏮🦑🐟🦑🫧"


def test_daily_wins_need_company_and_records_keep_the_best(db, seat):
    a, b, c = seat("ivan"), seat("judy"), seat("priya")
    code = a.post("/boards", {"name": "soup"}).json["invite"]["code"]
    for x in (b, c):
        x.post("/boards/join", {"code": code})
    for x in (a, b, c):
        x.put("/boards/soup/agenda/krillion")
    board = db.query(Board).one()
    viewer = db.query(Person).filter_by(username="ivan").one()
    day = reads.game_day("krillion", viewer, NOW)
    n = reads.REGISTRY["krillion"].current(NOW, viewer.tz)
    a.post("/pastes", {"text": KRILLION.format(n=n, score=300)})
    b.post("/pastes", {"text": KRILLION.format(n=n, score=280)})
    c.post("/pastes", {"text": KRILLION.format(n=n - 1, score=100)})  # alone yesterday: no win
    db.expire_all()

    today = reads.review(db, board, viewer, "today", now=NOW)
    print(today)
    assert [(x["nickname"], x["wins"], x["place"]) for x in today["standings"]][:2] == [("ivan", 1, 1), ("judy", 0, 2)]
    (k,) = today["games"]
    assert (k["present"], k["players"], k["place"], k["leader"]["nickname"]) == (2, 3, "1", "ivan")
    week = reads.review(db, board, viewer, "week", now=NOW)
    assert {x["nickname"]: x["days"] for x in week["standings"]} == {"ivan": 1, "judy": 1, "priya": 1}
    (rec,) = week["records"]
    assert (rec["nickname"], rec["day"]) == ("ivan", day.isoformat())
    assert a.get("/boards/soup/review?period=year").status_code == 400
