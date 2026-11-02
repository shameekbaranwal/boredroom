from datetime import datetime, timedelta, timezone

from boredroom import reads
from boredroom.models import Board, Person

from .conftest import NOW

WIKI = "Seawater ➡️ Babe Ruth ⏰ 02:09 🦶5 🔗 https://www.thewikigamedaily.com"
WIKI_ROUTE = ("Seawater ➡️ Babe Ruth ⏰ 01:50 🦶4 (Seawater ➡️ ASTM International ➡️ Babe Ruth) "
              "🔗 https://www.thewikigamedaily.com")
MAPTAP = "www.maptap.gg October 30\n90🎯 90🎯 90🎯 90🎯 90🎯\nFinal score: {}"


def board_of(seat):
    a, b, c = seat("ivan"), seat("judy"), seat("dev")
    code = a.post("/boards", {"name": "soup"}).json["invite"]["code"]
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
    # maptap resets at the player's midnight
    assert mt["resets_at"] == "2026-10-31T00:00:00+05:30"


def test_today_says_how_much_the_board_plays_each_game(db, seat):
    a, b, c = board_of(seat)
    from boredroom import filing
    ivan, judy = (db.query(Person).filter_by(username=n).one() for n in ("ivan", "judy"))
    filing.file_paste(db, ivan, WIKI, now=NOW)
    filing.file_paste(db, judy, WIKI, now=NOW)
    filing.file_paste(db, ivan, MAPTAP.format(900), now=NOW)
    db.commit()
    t = reads.today(db, db.query(Board).one(), ivan, now=NOW)
    assert {i["game"]: (i["board_month"], i["results"]) for i in t["items"]} == {"wiki": (2, 1), "maptap": (1, 1)}
    # forty days on, none of it counts as lately
    later = reads.today(db, db.query(Board).one(), ivan, now=NOW + timedelta(days=40))
    assert {i["board_month"] for i in later["items"]} == {0}


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


def test_invite_preview_needs_no_sign_in(client, seat):
    a = seat("ivan")
    code = a.post("/boards", {"name": "soup"}).json["invite"]["code"]
    a.put("/boards/soup/agenda/wiki")
    assert client.get(f"/api/v1/invites/{code}").json == {
        "code": code, "name": "soup", "slug": "soup", "chair": "ivan", "inviter": "ivan", "members": 1, "library": ["wiki game"], "seats": []}
    assert client.get("/api/v1/invites/nope").status_code == 404


def test_the_agenda_puts_your_most_filed_games_first(db, seat):
    a, b, c = board_of(seat)
    from boredroom import filing
    ivan = db.query(Person).filter_by(username="ivan").one()
    for back in (1, 2):  # two old maptaps, no wiki games: maptap outranks wiki's earlier reset
        old = MAPTAP.replace("October 30", f"October {30 - back}").format(800)
        filing.file_paste(db, ivan, old, now=NOW - timedelta(days=back))
    db.commit()
    t = reads.today(db, db.query(Board).one(), ivan, now=NOW)
    assert [(i["game"], i["results"]) for i in t["items"]] == [("maptap", 2), ("wiki", 0)]


def test_username_check(seat, client):
    a = seat("ivan")
    check = lambda n, who=None: (who.get(f"/usernames/{n}") if who else client.get(f"/api/v1/usernames/{n}")).json  # noqa: E731
    assert check("ivan") == {"username": "ivan", "available": False, "reason": "taken"}
    assert check("IVAN", a)["reason"] == "that's you"
    assert check("priya")["available"] is True
    assert check("x")["available"] is False


def test_every_response_carries_security_headers(seat):
    a = seat("ivan")
    r = a.get("/me")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Cache-Control"] == "no-store"


def test_a_skip_lasts_until_the_reset_and_undoes(db, seat):
    a, b, c = board_of(seat)
    a.post("/boards", {"name": "stew"})
    a.put("/boards/stew/agenda/wiki")
    skipped = lambda r: {i["game"]: i["skipped"] for i in r.json["items"]}  # noqa: E731
    assert skipped(a.put("/boards/soup/skips/wiki")) == {"wiki": True, "maptap": False}
    assert skipped(a.get("/boards/stew/today")) == {"wiki": True}  # sat out on every board
    assert skipped(b.get("/boards/soup/today")) == {"wiki": False}  # and only by you
    assert skipped(a.delete("/boards/soup/skips/wiki")) == {"wiki": False, "maptap": False}
    assert a.put("/boards/soup/skips/nonsense").status_code == 404

    # filing wins over a skip, and the next day brings the game back
    from boredroom import filing
    ivan = db.query(Person).filter_by(username="ivan").one()
    board = db.query(Board).filter_by(slug="soup").one()
    reads.skip(db, ivan, "maptap", True, now=NOW)
    reads.skip(db, ivan, "wiki", True, now=NOW)
    db.commit()
    assert {i["game"]: i["skipped"] for i in reads.today(db, board, ivan, now=NOW)["items"]} == {"wiki": True, "maptap": True}
    filing.file_paste(db, ivan, MAPTAP.format(900), now=NOW)
    db.commit()
    t = {i["game"]: (i["filed"], i["skipped"]) for i in reads.today(db, board, ivan, now=NOW)["items"]}
    assert t == {"wiki": (False, True), "maptap": (True, False)}
    tomorrow = reads.today(db, board, ivan, now=NOW + timedelta(days=1))
    assert {i["skipped"] for i in tomorrow["items"]} == {False}
