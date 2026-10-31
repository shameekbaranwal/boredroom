def test_guest_gets_a_token_and_me_needs_it(client, seat):
    a = seat("ivan")
    assert a.get("/me").json == {"username": "ivan", "kind": "guest", "tz": "Asia/Kolkata", "email": None, "boards": []}
    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/me", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_usernames_are_checked(client, seat):
    seat("ivan")
    assert client.post("/api/v1/guests", json={"username": "ivan"}).status_code == 409
    assert client.post("/api/v1/guests", json={"username": "A Run!"}).status_code == 400
    anon = client.post("/api/v1/guests", json={})
    assert anon.status_code == 201 and anon.json["me"]["username"].startswith("guest-")


def test_timezone_is_editable_and_validated(seat):
    a = seat("olv")
    assert a.patch("/me", {"tz": "Asia/Singapore"}).json["tz"] == "Asia/Singapore"
    assert a.patch("/me", {"tz": "Mars/Olympus"}).status_code == 400


def test_create_join_and_nickname(seat):
    chair, judy = seat("shmk"), seat("judy")
    b = chair.post("/boards", {"name": "Soup"}).json
    assert (b["slug"], b["name"], b["you"]["role"]) == ("soup", "soup", "chair")
    assert chair.post("/boards", {"name": "soup"}).json["slug"] == "soup-2"

    assert judy.get("/boards/soup").status_code == 404  # not a member yet
    assert judy.post("/boards/join", {"code": "wrong"}).status_code == 404
    joined = judy.post("/boards/join", {"code": b["invite"]["code"]}).json
    assert joined["you"] == {"nickname": "judy", "role": "member", "agenda": []}
    assert judy.patch("/boards/soup/me", {"nickname": "j0dy"}).json["you"]["nickname"] == "j0dy"
    assert [m["nickname"] for m in chair.get("/boards/soup").json["members"]] == ["j0dy", "shmk"]
    assert [x["slug"] for x in judy.get("/me").json["boards"]] == ["soup"]


def test_agenda_adds_to_library_and_only_chair_removes(seat):
    chair, ivan = seat("shmk"), seat("ivan")
    code = chair.post("/boards", {"name": "soup"}).json["invite"]["code"]
    ivan.post("/boards/join", {"code": code})

    b = ivan.put("/boards/soup/agenda/krillion").json
    assert b["you"]["agenda"] == ["krillion"]
    assert [(g["game"], g["players"]) for g in b["library"]] == [("krillion", 1)]
    assert ivan.put("/boards/soup/agenda/notagame").status_code == 404
    assert ivan.put("/boards/soup/library/maptap").status_code == 200

    assert ivan.delete("/boards/soup/library/krillion").status_code == 403
    after = chair.delete("/boards/soup/library/krillion").json
    assert [g["game"] for g in after["library"]] == ["maptap"]
    assert ivan.get("/boards/soup").json["you"]["agenda"] == []  # dropped with the game
