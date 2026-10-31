from datetime import datetime
from zoneinfo import ZoneInfo

from boredroom import invites
from boredroom.models import Board, Person, Result
from boredroom.seed import seed

IST = ZoneInfo("Asia/Kolkata")
KRILL = "Krillion #{} 🦐\n{}\n\n🐟🐟🏮🦑🐟🦑🫧"
WIKI = "Seawater ➡️ Babe Ruth ⏰ 02:09 🦶5 🔗 https://www.thewikigamedaily.com"


def at(day, h, m):
    return datetime(2026, 10, day, h, m, tzinfo=IST)


HISTORY = [
    (at(29, 9, 12), "tara", "Asia/Kolkata", KRILL.format(106, 300)),
    (at(29, 9, 15), "kabir", "Asia/Singapore", WIKI),
    (at(29, 9, 20), "tara", "Asia/Kolkata", "lol"),
    (at(30, 10, 1), "meera", "Asia/Kolkata", KRILL.format(107, 285)),
]


def test_seed_then_claim(db, seat):
    stats = seed(db, "soup", HISTORY)
    db.commit()
    assert (stats["members"], stats["filed"]) == (3, 3)
    assert seed(db, "soup", HISTORY)["duplicate"] == 3  # re-run
    db.commit()
    people = {p.username: p for p in db.query(Person)}
    assert people["kabir"].tz == "Asia/Singapore"
    board = db.query(Board).one()
    placeholder_id = people["tara"].id
    assert board.chair_id == placeholder_id  # the first name holds the chair

    a = seat("tara.k")
    a.post("/boards/join", {"code": invites.current(db, board).code})
    seen = a.get("/boards/soup").json["members"]
    assert {m["username"]: m["kind"] for m in seen}["tara"] == "placeholder"
    r = a.post("/boards/soup/claim", {"username": "tara"})
    assert r.status_code == 200 and r.json["moved"] == 1
    you = r.json["board"]["you"]
    assert (you["role"], you["agenda"]) == ("chair", ["krillion"])
    assert [x["game"] for x in a.get("/results").json] == ["krillion"]
    assert a.post("/boards/soup/claim", {"username": "tara"}).status_code == 409  # one seat each
    db.expire_all()
    assert db.get(Board, board.id).chair_id != placeholder_id
    assert db.get(Person, placeholder_id) is None
    assert db.query(Result).count() == 3


def test_the_chair_can_be_named(db):
    seed(db, "soup", HISTORY, chair="meera")
    db.commit()
    board = db.query(Board).one()
    assert db.get(Person, board.chair_id).username == "meera"


def test_a_reseed_files_new_messages_to_whoever_claimed_the_seat(db, seat):
    seed(db, "soup", HISTORY)
    db.commit()
    a = seat("tara.k")
    a.post("/boards/join", {"code": invites.current(db, db.query(Board).one()).code})
    a.post("/boards/soup/claim", {"username": "tara"})
    # the chat goes on; tara posts again, and the history is seeded again
    stats = seed(db, "soup", HISTORY + [(at(31, 9, 40), "tara", "Asia/Kolkata", KRILL.format(108, 410))])
    db.commit()
    assert (stats["filed"], stats["duplicate"]) == (1, 3)
    assert not db.query(Person).filter_by(kind="placeholder", username="tara").first()
    assert sorted(x["puzzle"] for x in a.get("/results").json) == ["106", "108"]


def test_join_and_claim_in_one_step(db, seat, client):
    seed(db, "soup", HISTORY)
    db.commit()
    code = invites.current(db, db.query(Board).one()).code
    seats = client.get(f"/api/v1/invites/{code}").json["seats"]
    assert sorted((s["nickname"], s["results"]) for s in seats) == [("kabir", 1), ("meera", 1), ("tara", 1)]

    a = seat("tara.k")
    r = a.post("/boards/join", {"code": code, "claim": "tara"})
    assert r.status_code == 200
    you = r.json["you"]
    assert (you["nickname"], you["role"], you["agenda"]) == ("tara", "chair", ["krillion"])
    assert len(client.get(f"/api/v1/invites/{code}").json["seats"]) == 2
    assert seat("bo").post("/boards/join", {"code": code, "claim": "nobody"}).status_code == 404
