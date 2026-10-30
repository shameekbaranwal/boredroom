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
    assert first.json["me"] | {"boards": []} == {
        "username": "ivan.k", "kind": "account", "tz": "Asia/Singapore",
        "email": "ivan.k@gmail.com", "boards": []}
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


def test_an_existing_account_wins_over_the_guest_seat(app, client, seat):
    google(app, IVAN)
    sign_in(client, "good:0")
    g = seat("drifter")
    me = sign_in(client, "good:0", token=g.headers["Authorization"][7:]).json["me"]
    assert me["username"] == "ivan.k"
    assert g.get("/me").json["kind"] == "guest"


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
