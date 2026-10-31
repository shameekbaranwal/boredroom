import sys
from pathlib import Path

from boredroom import invites
from boredroom.models import Board, Membership, Paste, Person, Result

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import import_chat  # noqa: E402

CHAT = """\
29/10/26, 09:12 - Mallory: Krillion #106 🦐
300

🐟🐟🏮🦑🐟🦑🫧
29/10/26, 09:15 - walter: Seawater ➡️ Babe Ruth ⏰ 02:09 🦶5 🔗 https://www.thewikigamedaily.com
"""
WIKI = "Seawater ➡️ Babe Ruth ⏰ 03:09 🦶6 🔗 https://www.thewikigamedaily.com"


def _soup(tmp_path, db):
    export = tmp_path / "chat.txt"
    export.write_text(CHAT, encoding="utf-8")
    import_chat.run(db, export, "soup", {}, "Asia/Kolkata")
    db.commit()
    return db.query(Board).one()


def _seats(r):
    return sorted((m["nickname"], m["kind"]) for m in r.json["members"])


def test_leaving_puts_a_claimed_seat_back_with_its_history(tmp_path, db, seat):
    board = _soup(tmp_path, db)
    a, s = seat("mallory.k"), seat("walter.b")
    code = invites.current(db, board).code
    a.post("/boards/join", {"code": code, "claim": "mallory"})  # mallory's seat holds the chair
    s.post("/boards/join", {"code": code})
    a.post("/pastes", {"text": WIKI})  # filed after claiming: stays mallory.k's
    assert a.post("/boards/soup/leave").json == {"left": "soup", "closed": False}

    r = s.get("/boards/soup")
    assert ("mallory", "placeholder") in _seats(r) and ("mallory.k", "guest") not in _seats(r)
    assert r.json["you"]["role"] == "chair"  # a person before an imported seat
    assert a.get("/boards/soup").status_code == 404
    assert {x["game"] for x in a.get("/results").json} == {"krillion", "wiki"}  # the leaver keeps theirs
    db.expire_all()
    back = db.query(Person).filter_by(username="mallory").one()
    assert [x.game_id for x in db.query(Result).filter_by(person_id=back.id)] == ["krillion"]
    assert db.query(Paste).filter_by(person_id=back.id).count() == 1
    assert "mallory" not in db.get(Board, board.id).settings["claimed"]

    # it can be claimed again, by anyone
    assert s.post("/boards/soup/claim", {"username": "mallory"}).json["moved"] == 1
    assert ("mallory", "placeholder") not in _seats(s.get("/boards/soup"))


def test_the_last_one_out_closes_the_board(seat):
    a = seat("ivan")
    a.post("/boards", {"name": "solo"})
    assert a.post("/boards/solo/leave").json["closed"] is True
    assert a.get("/me").json["boards"] == []


def test_closing_an_account_takes_it_all_but_the_chat_seat(tmp_path, db, seat):
    board = _soup(tmp_path, db)
    a = seat("mallory.k")
    a.post("/boards/join", {"code": invites.current(db, board).code, "claim": "mallory"})
    a.post("/pastes", {"text": WIKI})
    assert a.delete("/me").status_code == 400  # needs the username typed back
    r = a.client.delete("/api/v1/me", headers=a.headers, json={"username": "mallory.k"})
    assert r.json == {"deleted": True, "boards_closed": []}
    assert a.get("/me").status_code == 401
    db.expire_all()
    assert db.query(Person).filter_by(username="mallory.k").first() is None
    back = db.query(Person).filter_by(username="mallory").one()
    assert (back.kind, [x.game_id for x in db.query(Result).filter_by(person_id=back.id)]) == ("placeholder", ["krillion"])
    assert db.get(Board, board.id).chair_id == back.id  # the seat had the chair; it keeps it
    assert db.query(Membership).filter_by(person_id=back.id).one().role == "chair"


def test_the_board_says_what_leaving_would_do(tmp_path, db, seat):
    board = _soup(tmp_path, db)
    a = seat("mallory.k")
    r = a.post("/boards/join", {"code": invites.current(db, board).code, "claim": "mallory"})
    assert r.json["leaving"] == {"slug": "soup", "name": "soup", "chair": True,
                                 "claimed": {"nickname": "mallory", "results": 1}, "heir": "walter", "alone": False}
    assert a.get("/me/leaving").json == [r.json["leaving"]]
