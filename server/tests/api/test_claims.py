import sys
from pathlib import Path

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
    a.post("/boards/join", {"code": board.invite_code})
    seen = a.get("/boards/soup").json["members"]
    assert {m["username"]: m["kind"] for m in seen}["mallory"] == "placeholder"
    r = a.post("/boards/soup/claim", {"username": "mallory"})
    assert r.status_code == 200 and r.json["moved"] == 1
    you = r.json["board"]["you"]
    assert (you["role"], you["agenda"]) == ("chair", ["krillion"])
    assert [x["game"] for x in a.get("/results").json] == ["krillion"]
    assert a.post("/boards/soup/claim", {"username": "mallory"}).status_code == 404  # once only
    db.expire_all()
    assert db.get(Board, board.id).chair_id != placeholder_id
    assert db.get(Person, placeholder_id) is None
    assert db.query(Result).count() == 3
