import sys
from pathlib import Path

from boredroom import invites
from boredroom.models import Board, Person, Result

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import import_chat  # noqa: E402

CHAT = """\
29/10/26, 09:12 - Mallory: Krillion #106 🦐
300

🐟🐟🏮🦑🐟🦑🫧
29/10/26, 09:15 - +65 9123 4567: Seawater ➡️ Babe Ruth ⏰ 02:09 🦶5 🔗 https://www.thewikigamedaily.com
29/10/26, 09:20 - Mallory: lol
30/10/26, 10:01 - walter: Krillion #107 🦐
285

🐟🐟🏮🦑🐟🦑🫧
30/10/26, 10:05 - Mallory: <Media omitted>
"""


def test_import_then_claim(tmp_path, db, seat):
    export = tmp_path / "chat.txt"
    export.write_text(CHAT, encoding="utf-8")
    stats = import_chat.run(db, export, "soup", {}, "Asia/Kolkata")
    db.commit()
    assert (stats["members"], stats["filed"]) == (3, 3)
    assert import_chat.run(db, export, "soup", {}, "Asia/Kolkata")["duplicate"] == 3  # re-run
    db.commit()
    people = {p.username: p for p in db.query(Person)}
    assert people["member-65"].tz == "Asia/Singapore"
    assert not any("9123" in u for u in people)  # the phone number isn't kept
    board = db.query(Board).one()
    placeholder_id = people["mallory"].id
    assert board.chair_id == placeholder_id  # first sender holds the chair

    a = seat("mallory.k")
    a.post("/boards/join", {"code": invites.current(db, board).code})
    seen = a.get("/boards/soup").json["members"]
    assert {m["username"]: m["kind"] for m in seen}["mallory"] == "placeholder"
    r = a.post("/boards/soup/claim", {"username": "mallory"})
    assert r.status_code == 200 and r.json["moved"] == 1
    you = r.json["board"]["you"]
    assert (you["role"], you["agenda"]) == ("chair", ["krillion"])
    assert [x["game"] for x in a.get("/results").json] == ["krillion"]
    assert a.post("/boards/soup/claim", {"username": "mallory"}).status_code == 409  # one seat each
    db.expire_all()
    assert db.get(Board, board.id).chair_id != placeholder_id
    assert db.get(Person, placeholder_id) is None
    assert db.query(Result).count() == 3


def test_a_reimport_files_new_messages_to_whoever_claimed_the_seat(tmp_path, db, seat):
    export = tmp_path / "chat.txt"
    export.write_text(CHAT, encoding="utf-8")
    import_chat.run(db, export, "soup", {}, "Asia/Kolkata")
    db.commit()
    a = seat("mallory.k")
    a.post("/boards/join", {"code": invites.current(db, db.query(Board).one()).code})
    a.post("/boards/soup/claim", {"username": "mallory"})
    # the chat goes on; mallory posts again, then it's exported and imported again
    export.write_text(CHAT + "31/10/26, 09:40 - Mallory: Krillion #108 🦐\n410\n\n🐟🦑🫧\n", encoding="utf-8")
    stats = import_chat.run(db, export, "soup", {}, "Asia/Kolkata")
    db.commit()
    assert (stats["filed"], stats["duplicate"]) == (1, 3)
    assert not db.query(Person).filter_by(kind="placeholder", username="mallory").first()
    assert sorted(x["puzzle"] for x in a.get("/results").json) == ["106", "108"]


def test_join_and_claim_in_one_step(tmp_path, db, seat, client):
    export = tmp_path / "chat.txt"
    export.write_text(CHAT, encoding="utf-8")
    import_chat.run(db, export, "soup", {}, "Asia/Kolkata")
    db.commit()
    code = invites.current(db, db.query(Board).one()).code
    seats = client.get(f"/api/v1/invites/{code}").json["seats"]
    assert sorted((s["nickname"], s["results"]) for s in seats) == [("mallory", 1), ("member (+65)", 1), ("walter", 1)]

    a = seat("mallory.k")
    r = a.post("/boards/join", {"code": code, "claim": "mallory"})
    assert r.status_code == 200
    you = r.json["you"]
    assert (you["nickname"], you["role"], you["agenda"]) == ("mallory", "chair", ["krillion"])
    assert len(client.get(f"/api/v1/invites/{code}").json["seats"]) == 2
    assert seat("bo").post("/boards/join", {"code": code, "claim": "nobody"}).status_code == 404
