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
    assert [(x["nickname"], x["wins"], x["place"]) for x in today["standings"]][:2] == [("ivan", 1, 1), ("judy", 0, None)]
    (k,) = today["games"]
    assert (k["present"], k["players"], k["place"], k["leader"]["nickname"]) == (2, 3, "1", "ivan")
    week = reads.review(db, board, viewer, "week", now=NOW)
    assert {x["nickname"]: x["days"] for x in week["standings"]} == {"ivan": 1, "judy": 1, "priya": 1}
    (rec,) = week["records"]
    assert (rec["nickname"], rec["day"]) == ("ivan", day.isoformat())
    assert a.get("/boards/soup/review?period=year").status_code == 400


def test_the_formula_bar_picks_a_game_a_stat_and_a_rival(db, seat):
    a, b = seat("ivan"), seat("judy")
    code = a.post("/boards", {"name": "soup"}).json["invite"]["code"]
    b.post("/boards/join", {"code": code})
    for x in (a, b):
        x.put("/boards/soup/agenda/krillion")
    board = db.query(Board).one()
    viewer = db.query(Person).filter_by(username="ivan").one()
    n = reads.REGISTRY["krillion"].current(NOW, viewer.tz)
    for back, (mine, theirs) in enumerate([(300, 280), (250, 290), (270, 270)]):
        a.post("/pastes", {"text": KRILLION.format(n=n - back, score=mine)})
        b.post("/pastes", {"text": KRILLION.format(n=n - back, score=theirs)})
    db.expire_all()

    g = reads.review(db, board, viewer, "week", game="krillion", now=NOW)
    assert (g["stat"], g["metric"], g["min_plays"]) == ("average", "score", 3)
    assert [(x["nickname"], x["average"], x["place"]) for x in g["standings"]] == [("judy", 280.0, 1), ("ivan", 273.33, 2)]
    assert g["record"]["metrics"] == {"score": 300}
    best = reads.review(db, board, viewer, "week", game="krillion", stat="best", now=NOW)
    assert [x["nickname"] for x in best["standings"]] == ["ivan", "judy"]
    v = reads.review(db, board, viewer, "all", vs="judy", now=NOW)
    assert v["h2h"] == {"you": 1, "them": 1, "level": 1}
    assert v["strip"][-3:] == ["lv", "ls", "on"]
    r = a.get("/boards/soup/review?period=all&stat=rate")
    assert [(x["nickname"], x["rate"]) for x in r.json["standings"]] == [("ivan", 0.667), ("judy", 0.667)]
    assert a.get("/boards/soup/review?game=wiki").status_code == 400
    assert a.get("/boards/soup/review?stat=average").status_code == 400


def test_tenure_counts_days_in_a_row():
    from datetime import date
    d = date(2026, 10, 30)
    days = {date(2026, 10, x) for x in (20, 21, 22, 23, 27, 28, 29)}
    assert reads.tenure(days, d) == (3, 4, True)  # alive through yesterday, at risk today
    assert reads.tenure(days | {d}, d) == (4, 4, False)
    assert reads.tenure({date(2026, 10, 27)}, d) == (0, 1, False)


def test_tenure_shows_on_the_agenda_minutes_and_review(db, seat):
    a = seat("ivan")
    a.post("/boards", {"name": "soup"})
    a.put("/boards/soup/agenda/krillion")
    viewer = db.query(Person).filter_by(username="ivan").one()
    n = reads.REGISTRY["krillion"].current(NOW, viewer.tz)
    for back in (1, 2, 3):
        a.post("/pastes", {"text": KRILLION.format(n=n - back, score=300)})
    db.expire_all()
    board = db.query(Board).one()
    (item,) = reads.today(db, board, viewer, now=NOW)["items"]
    assert item["tenure"] == {"days": 3, "at_risk": True}
    a.post("/pastes", {"text": KRILLION.format(n=n, score=300)})
    db.expire_all()
    day = reads.game_day("krillion", viewer, NOW)
    assert reads.minutes(db, board, viewer, "krillion", day, now=NOW)["rows"][0]["tenure"] == 4
    r = reads.review(db, board, viewer, "week", game="krillion", stat="tenure", now=NOW)
    assert (r["standings"][0]["tenure"], r["standings"][0]["longest"], r["standings"][0]["place"]) == (4, 4, 1)


def test_the_grid_shows_who_turned_up_and_who_won(db, seat):
    a, b, c, d = seat("ivan"), seat("judy"), seat("priya"), seat("trent")
    code = a.post("/boards", {"name": "soup"}).json["invite"]["code"]
    for x in (b, c, d):
        x.post("/boards/join", {"code": code})
    for x in (a, b, c, d):
        x.put("/boards/soup/agenda/krillion")
    board = db.query(Board).one()
    viewer = db.query(Person).filter_by(username="ivan").one()
    n = reads.REGISTRY["krillion"].current(NOW, viewer.tz)
    for back, (mine, theirs) in enumerate([(300, 280), (250, 290)]):
        a.post("/pastes", {"text": KRILLION.format(n=n - back, score=mine)})
        b.post("/pastes", {"text": KRILLION.format(n=n - back, score=theirs)})
    c.post("/pastes", {"text": KRILLION.format(n=n - 2, score=100)})  # alone: filed, no win
    db.expire_all()

    g = reads.review(db, board, viewer, "week", view="grid", now=NOW)["grid"]
    today = reads.game_day("krillion", viewer, NOW)
    assert len(g["days"]) == 7 and g["days"][-1] == today.isoformat()
    assert g["absent"] == 1  # trent filed nothing all week
    rows = {r["nickname"]: r for r in g["rows"]}
    assert [r["nickname"] for r in g["rows"]] == ["ivan", "judy", "priya"]  # the standings' order
    assert rows["ivan"]["cells"][-2:] == [{"v": 0, "f": 1}, {"v": 1, "f": 1}] and rows["ivan"]["total"] == 1
    assert rows["priya"]["cells"][-3] == {"v": 0, "f": 1} and rows["priya"]["cells"][-1] is None

    one = reads.review(db, board, viewer, "month", game="krillion", view="grid", now=NOW)["grid"]
    assert len(one["days"]) == 30
    rows = {r["nickname"]: r for r in one["rows"]}
    assert [(c["k"], c["m"]) for c in rows["ivan"]["cells"][-2:]] == [("played", {"score": 250}), ("top", {"score": 300})]
    assert rows["judy"]["total"] == 1
    assert rows["priya"]["cells"][0] == {"k": "off"}  # before she took krillion up: hatched, not absent
    assert rows["priya"]["cells"][-1] is None  # after: a plain gap
    assert a.get("/boards/soup/review?view=grid").status_code == 400  # today is one column
    assert a.get("/boards/soup/review?period=week&view=grid").json["grid"]["absent"] == 1
