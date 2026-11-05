from boredroom.auth import GoogleId
from boredroom.config import Config
from boredroom.errors import fail

IVAN = GoogleId("sub-ivan", "ivan.k@gmail.com", "Ivan K")


def google(app, *people):
    """Signs in with a fake verifier: credential "good:<n>" is people[n]."""
    app.config["BOREDROOM"] = Config(google_client_id="test-client.apps.googleusercontent.com")

    def verify(credential, client_id):
        assert client_id == "test-client.apps.googleusercontent.com"
        if not credential.startswith("good:"):
            fail(401, "google didn't vouch for that sign-in; try again")
        return people[int(credential[5:])]
    app.config["GOOGLE_VERIFY"] = verify


def sign_in(client, credential, token=None, tz=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post("/api/v1/auth/google", json={"credential": credential, "tz": tz}, headers=headers)


def test_config_exposes_only_the_client_id(app, client):
    assert client.get("/api/v1/config").json["google_client_id"] is None
    google(app, IVAN)
    assert client.get("/api/v1/config").json["google_client_id"] == "test-client.apps.googleusercontent.com"


def test_not_set_up_and_bad_credentials(app, client):
    assert sign_in(client, "good:0").status_code == 503
    google(app, IVAN)
    assert sign_in(client, "forged").status_code == 401
    assert client.post("/api/v1/auth/google", json={}).status_code == 400


def test_new_account_then_signing_in_again(app, client):
    google(app, IVAN, GoogleId("sub-other", "ivan.k@outlook.com", None))
    first = sign_in(client, "good:0", tz="Asia/Singapore")
    assert first.status_code == 201 and first.json["created"]
    assert first.json["me"] | {"boards": [], "news": None} == {  # news depends on the day: test_news.py
        "username": "ivan.k", "kind": "account", "tz": "Asia/Singapore",
        "email": "ivan.k@gmail.com", "agenda_sort": None, "reset_clock": False, "paste_check": True, "boards": [], "news": None}
    again = sign_in(client, "good:0")
    assert again.status_code == 200 and not again.json["created"]
    assert again.json["token"] != first.json["token"]  # one token per device
    # a different google account with the same local part gets a numbered username
    assert sign_in(client, "good:1").json["me"]["username"] == "ivan.k2"


def test_a_guest_seat_becomes_the_account_with_its_history(app, client, seat):
    google(app, IVAN)
    a = seat("ivan")
    a.post("/boards", {"name": "soup"})
    a.post("/pastes", {"text": "Krillion #107 🦐\n285\n\n🐟🐟🏮🦑🐟🦑🫧"})
    r = sign_in(client, "good:0", token=a.headers["Authorization"][7:])
    assert r.status_code == 200 and not r.json["created"]
    me = r.json["me"]
    assert (me["username"], me["kind"], [b["slug"] for b in me["boards"]]) == ("ivan", "account", ["soup"])
    after = {"Authorization": f"Bearer {r.json['token']}"}
    assert len(client.get("/api/v1/results", headers=after).json) == 1
    assert a.get("/me").json["kind"] == "account"  # the guest token still works


KRILL = "Krillion #{} 🦐\n{}\n\n🐟🐟🏮🦑🐟🦑🫧"


def test_a_guest_folds_into_an_account_that_already_exists(app, client, seat):
    google(app, IVAN)
    acct = {"Authorization": f"Bearer {sign_in(client, 'good:0').json['token']}"}
    client.post("/api/v1/pastes", json={"text": KRILL.format(107, 300)}, headers=acct)
    tea = client.post("/api/v1/boards", json={"name": "tea"}, headers=acct).json

    g = seat("drifter")  # on another device, as a guest: chairs soup, joins tea, files two krillions
    g.post("/boards", {"name": "soup"})
    g.put("/boards/soup/agenda/krillion")
    g.post("/boards/join", {"code": tea["invite"]["code"]})
    g.post("/pastes", {"text": KRILL.format(107, 250)})  # the account already has 107: the account's stays
    g.post("/pastes", {"text": KRILL.format(106, 280)})
    r = sign_in(client, "good:0", token=g.headers["Authorization"][7:])
    assert r.status_code == 200 and r.json["merged"] == {"results": 1, "boards": 1}

    me = r.json["me"]
    assert (me["username"], sorted(b["slug"] for b in me["boards"])) == ("ivan.k", ["soup", "tea"])
    after = {"Authorization": f"Bearer {r.json['token']}"}
    kept = {x["puzzle"]: x["metrics"] for x in client.get("/api/v1/results", headers=after).json}
    assert kept == {"107": {"score": 300}, "106": {"score": 280}}
    soup = client.get("/api/v1/boards/soup", headers=after).json
    assert (soup["you"]["role"], soup["you"]["agenda"]) == ("chair", ["krillion"])  # the chair comes along
    assert len(client.get("/api/v1/boards/tea", headers=after).json["members"]) == 1  # one seat, not two
    assert g.get("/me").json["username"] == "ivan.k"  # the guest's own token lands in the account


def test_an_account_signs_in_to_another_account_as_itself(app, client):
    google(app, IVAN, GoogleId("sub-other", "ivan.k@outlook.com", None))
    first = sign_in(client, "good:0").json["token"]
    r = sign_in(client, "good:1", token=first)  # only a guest folds in; an account is left alone
    assert (r.json["me"]["username"], r.json["merged"]) == ("ivan.k2", None)


def test_sign_out_revokes_the_token(seat):
    a = seat("ivan")
    assert a.post("/auth/signout").json == {"signed_out": True}
    assert a.get("/me").status_code == 401


def test_old_timezone_names_and_junk_never_block_sign_in(app, client):
    google(app, IVAN)
    me = sign_in(client, "good:0", tz="Asia/Calcutta").json["me"]
    assert me["tz"] == "Asia/Kolkata"
    r = client.post("/api/v1/guests", json={"username": "drifter", "tz": "Mars/Olympus"})
    assert r.status_code == 201 and r.json["me"]["tz"] == "Asia/Kolkata"
