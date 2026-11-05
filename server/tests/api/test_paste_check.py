from boredroom.models import Paste

from .test_filing import WIKI


def test_the_shortcut_files_with_its_own_key_and_answers_in_words(db, client, seat):
    a = seat("ivan")
    assert a.get("/me/shortcut").json == {"set": False, "used": None}
    key = a.post("/me/shortcut").json["key"]
    assert a.get("/me/shortcut").json["set"] is True

    r = client.post("/api/v1/shortcut", json={"key": key, "text": WIKI})
    assert r.status_code == 201 and r.mimetype == "text/plain"
    assert r.text.startswith("filed wiki") and "not on your agenda" in r.text
    assert db.query(Paste).one().source == "share"
    again = client.post("/api/v1/shortcut", json={"text": WIKI}, headers={"Authorization": f"Bearer {key}"})
    assert "already in the minutes" in again.text
    assert a.get("/me/shortcut").json["used"]

    # it only files: the rest of the api turns it away
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {key}"}).status_code == 403
    nothing = client.post("/api/v1/shortcut", json={"key": key, "text": "hello"})
    assert nothing.status_code == 201 and "nothing readable" in nothing.text
    assert client.post("/api/v1/shortcut", json={"key": key, "text": " "}).text == "paste something first"


def test_a_new_shortcut_key_retires_the_old_one(client, seat):
    a = seat("ivan")
    old = a.post("/me/shortcut").json["key"]
    new = a.post("/me/shortcut").json["key"]
    gone = client.post("/api/v1/shortcut", json={"key": old, "text": WIKI})
    assert gone.status_code == 401 and "make a new one" in gone.text
    assert client.post("/api/v1/shortcut", json={"key": new, "text": WIKI}).status_code == 201
    a.delete("/me/shortcut")
    assert client.post("/api/v1/shortcut", json={"key": new, "text": WIKI}).status_code == 401
    assert client.post("/api/v1/shortcut", json={"text": WIKI}).status_code == 401


def test_pasting_can_file_at_once(seat):
    a = seat("ivan")
    assert a.get("/me").json["paste_check"] is True
    assert a.patch("/me", {"paste_check": False}).json["paste_check"] is False
    assert a.patch("/me", {"paste_check": "no"}).status_code == 400
