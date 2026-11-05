def test_pasting_can_file_at_once(seat):
    a = seat("ivan")
    assert a.get("/me").json["paste_check"] is True
    assert a.patch("/me", {"paste_check": False}).json["paste_check"] is False
    assert a.patch("/me", {"paste_check": "no"}).status_code == 400
