from datetime import datetime, timezone

from boredroom import reads
from boredroom.models import Board, Person

from .conftest import NOW

WIKI = "Seawater ➡️ Babe Ruth ⏰ 02:09 🦶5 🔗 https://www.thewikigamedaily.com"
WIKI_ROUTE = ("Seawater ➡️ Babe Ruth ⏰ 01:50 🦶4 (Seawater ➡️ ASTM International ➡️ Babe Ruth) "
              "🔗 https://www.thewikigamedaily.com")
MAPTAP = "www.maptap.gg October 30\n90🎯 90🎯 90🎯 90🎯 90🎯\nFinal score: {}"


def board_of(seat):
    a, b, c = seat("ivan"), seat("judy"), seat("dev")
    code = a.post("/boards", {"name": "soup"}).json["invite_code"]
    for x in (b, c):
        x.post("/boards/join", {"code": code})
    for x in (a, b, c):
        x.put("/boards/soup/agenda/wiki")
    a.put("/boards/soup/agenda/maptap")
    return a, b, c


def test_minutes_hide_details_until_you_file(db, seat):
    a, b, c = board_of(seat)
    from boredroom import filing
    ivan, judy = (db.query(Person).filter_by(username=n).one() for n in ("ivan", "judy"))
    filing.file_paste(db, ivan, WIKI_ROUTE, now=NOW)
    filing.file_paste(db, judy, WIKI, now=NOW)
    db.commit()
    board = db.query(Board).one()
    dev = db.query(Person).filter_by(username="dev").one()

    unseen = reads.minutes(db, board, dev, "wiki", None, now=NOW)
    assert unseen["open"] is False and unseen["not_in"] == ["dev"]
    top = unseen["rows"][0]
    assert (top["nickname"], top["place"], top["metrics"]) == ("ivan", "1", {"steps": 4, "time": 110})
    assert top["raw"] is None and top["hidden"] == 2
    assert [f["name"] for f in top["fields"]] == []

    seen = reads.minutes(db, board, judy, "wiki", None, now=NOW)
    assert seen["open"] and [f["name"] for f in seen["rows"][0]["fields"]] == ["pages", "route"]
    assert seen["rows"][1]["me"] and seen["rows"][1]["id"] is not None
    assert seen["rows"][0]["id"] is None  # others' result ids aren't handed out


def test_today_sorts_open_first_and_places(db, seat):
    a, b, c = board_of(seat)
    from boredroom import filing
    ivan = db.query(Person).filter_by(username="ivan").one()
    filing.file_paste(db, ivan, MAPTAP.format(900), now=NOW)
    db.commit()
    t = reads.today(db, db.query(Board).one(), ivan, now=NOW)
    assert [(i["game"], i["filed"], i["place"]) for i in t["items"]] == [("wiki", False, ""), ("maptap", True, "1")]
    mt = t["items"][1]
    assert (mt["present"], mt["players"], mt["leader"]["nickname"]) == (1, 1, "ivan")
    # maptap resets at utc midnight: 05:30 ist on the 31st
    assert mt["resets_at"] == "2026-10-31T00:00:00+00:00"


def test_endpoints(seat):
    a, b, c = board_of(seat)
    a.post("/pastes", {"text": WIKI})
    today = a.get("/boards/soup/today").json
    assert {i["game"] for i in today["items"]} == {"wiki", "maptap"}
    day = next(i["day"] for i in today["items"] if i["game"] == "wiki")
    m = b.get(f"/boards/soup/minutes/wiki?day={day}").json
    assert [r["nickname"] for r in m["rows"]] == ["ivan"] and m["open"] is False
    assert b.get("/boards/soup/minutes/nope").status_code in (400, 404)
    assert b.get("/boards/soup/minutes/wiki?day=yesterday").status_code == 400


def test_next_reset_for_a_local_midnight_game():
    p = Person(username="x", tz="Asia/Kolkata")
    at = reads.next_reset("wordle", p, datetime(2026, 10, 30, 20, 0, tzinfo=timezone.utc))
    assert at.isoformat() == "2026-11-01T00:00:00+05:30"
