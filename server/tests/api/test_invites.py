from datetime import datetime, timedelta
from urllib.parse import quote

from boredroom import invites
from boredroom.models import Board, Invite, utcnow


def test_a_new_board_hands_out_three_words(seat):
    code = seat("ivan").post("/boards", {"name": "soup"}).json["invite"]["code"]
    adj, noun, verb = code.split("-")
    assert adj in invites.ADJECTIVES and noun in invites.NOUNS and verb in invites.VERBS


def test_the_words_forgive_case_spacing_and_a_pasted_link(client, seat):
    code = seat("ivan").post("/boards", {"name": "soup"}).json["invite"]["code"]
    for t in (code.upper().replace("-", " "), f"  {code.replace('-', ', ')} "):
        assert client.get(f"/api/v1/invites/{quote(t)}").json["slug"] == "soup", t
    link = f"https://boredroom.shmk.dev/join/{code}"
    assert seat("bea").post("/boards/join", {"code": link}).json["slug"] == "soup"


def test_old_random_codes_still_work_exactly_as_typed(client, db, seat):
    seat("ivan").post("/boards", {"name": "soup"})
    board = db.query(Board).one()
    db.add(Invite(code="Ab3_xYz9QrSt", board_id=board.id, legacy=True))
    db.commit()
    assert client.get("/api/v1/invites/Ab3_xYz9QrSt").status_code == 200
    assert client.get("/api/v1/invites/ab3_xyz9qrst").status_code == 404


def test_expired_and_revoked_invites_stop_working_and_a_fresh_one_is_made(client, db, seat):
    a = seat("ivan")
    code = a.post("/boards", {"name": "soup"}).json["invite"]["code"]
    inv = db.query(Invite).filter_by(code=code).one()
    inv.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    assert client.get(f"/api/v1/invites/{code}").status_code == 404
    fresh = a.get("/boards/soup").json["invite"]["code"]
    assert fresh != code and a.get("/boards/soup").json["invite"]["code"] == fresh  # made once, then kept
    db.query(Invite).filter_by(code=fresh).one().revoked_at = utcnow()
    db.commit()
    assert seat("bea").post("/boards/join", {"code": fresh}).status_code == 404


def test_someone_guessing_codes_is_slowed_down(client, seat):
    code = seat("ivan").post("/boards", {"name": "soup"}).json["invite"]["code"]
    for _ in range(invites.MISS_LIMIT):
        assert client.get("/api/v1/invites/smug-walrus-nopes").status_code == 404
    assert client.get(f"/api/v1/invites/{code}").status_code == 429


def test_each_member_hands_out_their_own_invite_for_a_day(client, seat):
    a = seat("ivan")
    mine = a.post("/boards", {"name": "soup"}).json["invite"]
    b = seat("bea")
    b.post("/boards/join", {"code": mine["code"]})
    theirs = b.get("/boards/soup").json["invite"]
    assert theirs["code"] != mine["code"]
    assert client.get(f"/api/v1/invites/{theirs['code']}").json["inviter"] == "bea"
    left = datetime.fromisoformat(theirs["expires_at"]) - utcnow()
    assert timedelta(hours=23) < left <= timedelta(hours=24)


def test_a_new_link_retires_the_old_one(client, seat):
    a = seat("ivan")
    old = a.post("/boards", {"name": "soup"}).json["invite"]["code"]
    new = a.post("/boards/soup/invite").json["invite"]["code"]
    assert new != old and a.get("/boards/soup").json["invite"]["code"] == new
    assert client.get(f"/api/v1/invites/{old}").status_code == 404
    assert client.get(f"/api/v1/invites/{new}").status_code == 200


def test_the_chair_renames_the_board_and_retires_every_invite(client, seat):
    a = seat("ivan")
    old = a.post("/boards", {"name": "soup"}).json["invite"]["code"]
    b = seat("bea")
    b.post("/boards/join", {"code": old})
    theirs = b.get("/boards/soup").json["invite"]["code"]
    assert b.patch("/boards/soup", {"name": "broth"}).status_code == 403
    assert b.delete("/boards/soup/invites").status_code == 403
    assert a.patch("/boards/soup", {"name": "Broth"}).json["name"] == "broth"
    r = a.delete("/boards/soup/invites").json
    assert r["retired"] == 2 and r["board"]["invite"]["code"] not in (old, theirs)
    assert client.get(f"/api/v1/invites/{theirs}").status_code == 404


def test_names_lose_hidden_characters_and_stay_unique_on_a_board(seat):
    a, b = seat("ivan"), seat("judy")
    code = a.post("/boards", {"name": "Soup‮​  Daily\x00"}).json["invite"]["code"]
    assert a.get("/me").json["boards"][0]["name"] == "soup daily"
    b.post("/boards/join", {"code": code})
    r = b.patch("/boards/soup-daily/me", {"nickname": "IVAN"})
    assert r.status_code == 409
    assert b.patch("/boards/soup-daily/me", {"nickname": "​"}).status_code == 400
    assert a.post("/boards", {"name": "स्वाद"}).json["slug"] != a.post("/boards", {"name": "स्वाद"}).json["slug"]
