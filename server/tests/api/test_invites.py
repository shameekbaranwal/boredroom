from datetime import timedelta
from urllib.parse import quote

from boredroom import invites
from boredroom.models import Board, Invite, utcnow


def test_a_new_board_hands_out_three_words(seat):
    code = seat("ivan").post("/boards", {"name": "soup"}).json["invite_code"]
    adj, noun, verb = code.split("-")
    assert adj in invites.ADJECTIVES and noun in invites.NOUNS and verb in invites.VERBS


def test_the_words_forgive_case_spacing_and_a_pasted_link(client, seat):
    code = seat("ivan").post("/boards", {"name": "soup"}).json["invite_code"]
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
    code = a.post("/boards", {"name": "soup"}).json["invite_code"]
    inv = db.query(Invite).filter_by(code=code).one()
    inv.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    assert client.get(f"/api/v1/invites/{code}").status_code == 404
    fresh = a.get("/boards/soup").json["invite_code"]
    assert fresh != code and a.get("/boards/soup").json["invite_code"] == fresh  # made once, then kept
    db.query(Invite).filter_by(code=fresh).one().revoked_at = utcnow()
    db.commit()
    assert seat("bea").post("/boards/join", {"code": fresh}).status_code == 404


def test_someone_guessing_codes_is_slowed_down(client, seat):
    code = seat("ivan").post("/boards", {"name": "soup"}).json["invite_code"]
    for _ in range(invites.MISS_LIMIT):
        assert client.get("/api/v1/invites/smug-walrus-nopes").status_code == 404
    assert client.get(f"/api/v1/invites/{code}").status_code == 429
