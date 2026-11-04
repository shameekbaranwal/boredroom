import re
def test_guest_gets_a_token_and_me_needs_it(client, seat):
    a = seat("ivan")
    assert a.get("/me").json | {"news": None} == {  # news depends on the day: test_news.py
        "username": "ivan", "kind": "guest", "tz": "Asia/Kolkata", "email": None, "agenda_sort": None, "reset_clock": False,
        "boards": [], "news": None}
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
    assert re.fullmatch(r"soup-[0-9a-f]{4}", chair.post("/boards", {"name": "soup"}).json["slug"])

    assert judy.get("/boards/soup").status_code == 404  # not a member yet
    assert judy.post("/boards/join", {"code": "wrong"}).status_code == 404
    joined = judy.post("/boards/join", {"code": b["invite"]["code"]}).json
    assert joined["you"] == {"nickname": "judy", "role": "member", "agenda": [], "claimed": False,
                             "digest": True, "nudges": [], "order": []}
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

    chair.put("/boards/soup/agenda/krillion")  # someone else plays it now: ivan can't take it back
    assert [g["removable"] for g in ivan.get("/boards/soup").json["library"]] == [False, True]
    assert ivan.delete("/boards/soup/library/krillion").status_code == 403
    after = chair.delete("/boards/soup/library/krillion").json
    assert [g["game"] for g in after["library"]] == ["maptap"]
    assert ivan.get("/boards/soup").json["you"]["agenda"] == []  # dropped with the game


def test_whoever_added_a_game_can_undo_it_until_someone_else_plays_it(seat):
    chair, ivan, ana = seat("shmk"), seat("ivan"), seat("ana")
    code = chair.post("/boards", {"name": "soup"}).json["invite"]["code"]
    ivan.post("/boards/join", {"code": code})
    ana.post("/boards/join", {"code": code})

    assert ivan.put("/boards/soup/agenda/krillion").json["library"][0]["removable"] is True
    assert ana.get("/boards/soup").json["library"][0]["removable"] is False  # not ana's to undo
    assert ana.delete("/boards/soup/library/krillion").status_code == 403
    gone = ivan.delete("/boards/soup/library/krillion").json  # the undo
    assert gone["library"] == [] and gone["you"]["agenda"] == []


def test_members_carry_what_they_have_on_file(seat):
    chair, ivan = seat("shmk"), seat("ivan")
    code = chair.post("/boards", {"name": "soup"}).json["invite"]["code"]
    ivan.post("/boards/join", {"code": code})
    ivan.post("/pastes", {"text": "Krillion #106 🦐\n300\n\n🐟🐟🏮🦑🐟🦑🫧"})
    ivan.put("/boards/soup/agenda/krillion")
    ms = {m["nickname"]: m for m in chair.get("/boards/soup").json["members"]}
    assert (ms["ivan"]["results"], ms["shmk"]["results"]) == (1, 0)
    assert ms["shmk"]["joined_at"] <= ms["ivan"]["joined_at"]


def test_the_agenda_sort_goes_with_you(client, seat):
    a = seat("trent")
    assert a.get("/me").json["agenda_sort"] is None
    assert a.patch("/me", {"agenda_sort": "resets:last"}).json["agenda_sort"] == "resets:last"
    # another device: nothing in common but the seat
    assert client.application.test_client().get("/api/v1/me", headers=a.headers).json["agenda_sort"] == "resets:last"
    assert a.patch("/me", {"agenda_sort": "usual:first"}).json["agenda_sort"] is None  # the usual is no setting
    for bad in ("shoe size:first", "resets:sideways", 7):
        assert a.patch("/me", {"agenda_sort": bad}).status_code == 400
    assert a.patch("/me", {"agenda_sort": None}).json["agenda_sort"] is None


def test_resets_as_a_clock_time(seat):
    a = seat("ivan")
    assert a.get("/me").json["reset_clock"] is False
    assert a.patch("/me", {"reset_clock": True}).json["reset_clock"] is True
    assert a.patch("/me", {"reset_clock": "yes"}).status_code == 400



def test_your_own_agenda_order(seat):
    a, b = seat("trent"), seat("judy")
    code = a.post("/boards", {"name": "soup"}).json["invite"]["code"]
    b.post("/boards/join", {"code": code})
    for g in ("wordle", "krillion", "mini", "connections"):
        a.put(f"/boards/soup/agenda/{g}")
    b.put("/boards/soup/agenda/wordle")
    # nothing placed yet: by name
    assert a.get("/boards/soup").json["you"]["order"] == ["connections", "krillion", "mini", "wordle"]  # "nyt mini"
    # the ones you place come first; the rest keep their turn; strangers to your agenda are ignored
    out = a.put("/boards/soup/order", {"games": ["mini", "wordle", "anno", "mini"]}).json["you"]
    assert out["order"] == ["mini", "wordle", "connections", "krillion"]
    assert out["agenda"] == ["connections", "krillion", "mini", "wordle"]  # still the plain list
    items = a.get("/boards/soup/today").json["items"]
    assert sorted((i["position"], i["game"]) for i in items) == [(0, "mini"), (1, "wordle"), (2, "connections"), (3, "krillion")]
    # a game you add later goes at the end
    a.put("/boards/soup/agenda/strands")
    assert a.get("/boards/soup").json["you"]["order"][-1] == "strands"
    # yours alone
    assert b.get("/boards/soup").json["you"]["order"] == ["wordle"]
    assert a.put("/boards/soup/order", {"games": "mini"}).status_code == 400
    assert a.patch("/me", {"agenda_sort": "own:first"}).json["agenda_sort"] == "own:first"
