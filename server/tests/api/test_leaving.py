from datetime import datetime
from zoneinfo import ZoneInfo

from boredroom import invites
from boredroom.models import Board, Membership, Paste, Person, Result
from boredroom.seed import seed

IST = ZoneInfo("Asia/Kolkata")
HISTORY = [
    (datetime(2026, 10, 29, 9, 12, tzinfo=IST), "tara", "Asia/Kolkata", "Krillion #106 🦐\n300\n\n🐟🐟🏮🦑🐟🦑🫧"),
    (datetime(2026, 10, 29, 9, 15, tzinfo=IST), "meera", "Asia/Kolkata",
     "Seawater ➡️ Babe Ruth ⏰ 02:09 🦶5 🔗 https://www.thewikigamedaily.com"),
]
WIKI = "Seawater ➡️ Babe Ruth ⏰ 03:09 🦶6 🔗 https://www.thewikigamedaily.com"


def _soup(tmp_path, db):
    seed(db, "soup", HISTORY)
    db.commit()
    return db.query(Board).one()


def _seats(r):
    return sorted((m["nickname"], m["kind"]) for m in r.json["members"])


def test_leaving_puts_a_claimed_seat_back_with_its_history(tmp_path, db, seat):
    board = _soup(tmp_path, db)
    a, s = seat("tara.k"), seat("meera.b")
    code = invites.current(db, board).code
    a.post("/boards/join", {"code": code, "claim": "tara"})  # tara's seat holds the chair
    s.post("/boards/join", {"code": code})
    a.post("/pastes", {"text": WIKI})  # filed after claiming: stays tara.k's
    assert a.post("/boards/soup/leave").json == {"left": "soup", "closed": False}

    r = s.get("/boards/soup")
    assert ("tara", "placeholder") in _seats(r) and ("tara.k", "guest") not in _seats(r)
    assert r.json["you"]["role"] == "chair"  # a person before an imported seat
    assert a.get("/boards/soup").status_code == 404
    assert {x["game"] for x in a.get("/results").json} == {"krillion", "wiki"}  # the leaver keeps theirs
    db.expire_all()
    back = db.query(Person).filter_by(username="tara").one()
    assert [x.game_id for x in db.query(Result).filter_by(person_id=back.id)] == ["krillion"]
    assert db.query(Paste).filter_by(person_id=back.id).count() == 1
    assert "tara" not in db.get(Board, board.id).settings["claimed"]

    # it can be claimed again, by anyone
    assert s.post("/boards/soup/claim", {"username": "tara"}).json["moved"] == 1
    assert ("tara", "placeholder") not in _seats(s.get("/boards/soup"))


def test_the_last_one_out_closes_the_board(seat):
    a = seat("ivan")
    a.post("/boards", {"name": "solo"})
    assert a.post("/boards/solo/leave").json["closed"] is True
    assert a.get("/me").json["boards"] == []


def test_closing_an_account_takes_it_all_but_the_chat_seat(tmp_path, db, seat):
    board = _soup(tmp_path, db)
    a = seat("tara.k")
    a.post("/boards/join", {"code": invites.current(db, board).code, "claim": "tara"})
    a.post("/pastes", {"text": WIKI})
    assert a.delete("/me").status_code == 400  # needs the username typed back
    r = a.client.delete("/api/v1/me", headers=a.headers, json={"username": "tara.k"})
    assert r.json == {"deleted": True, "boards_closed": []}
    assert a.get("/me").status_code == 401
    db.expire_all()
    assert db.query(Person).filter_by(username="tara.k").first() is None
    back = db.query(Person).filter_by(username="tara").one()
    assert (back.kind, [x.game_id for x in db.query(Result).filter_by(person_id=back.id)]) == ("placeholder", ["krillion"])
    assert db.get(Board, board.id).chair_id == back.id  # the seat had the chair; it keeps it
    assert db.query(Membership).filter_by(person_id=back.id).one().role == "chair"


def test_the_board_says_what_leaving_would_do(tmp_path, db, seat):
    board = _soup(tmp_path, db)
    a = seat("tara.k")
    r = a.post("/boards/join", {"code": invites.current(db, board).code, "claim": "tara"})
    assert r.json["leaving"] == {"slug": "soup", "name": "soup", "chair": True,
                                 "claimed": {"nickname": "tara", "results": 1}, "heir": "meera", "alone": False}
    assert a.get("/me/leaving").json == [r.json["leaving"]]


def test_one_claimed_seat_each(tmp_path, db, seat):
    board = _soup(tmp_path, db)
    a = seat("tara.k")
    a.post("/boards/join", {"code": invites.current(db, board).code, "claim": "tara"})
    r = a.post("/boards/soup/claim", {"username": "meera"})
    assert r.status_code == 409 and "one each" in r.json["error"]
    assert ("meera", "placeholder") in _seats(a.get("/boards/soup"))


def test_claiming_the_chairs_seat_doesnt_hand_over_the_chair(tmp_path, db, seat):
    board = _soup(tmp_path, db)  # tara's seat holds the chair
    code = invites.current(db, board).code
    s, x = seat("meera.b"), seat("stranger")
    s.post("/boards/join", {"code": code})
    r = x.post("/boards/join", {"code": code, "claim": "tara"})
    assert r.json["you"]["role"] == "member"
    assert s.get("/boards/soup").json["you"]["role"] == "chair"
