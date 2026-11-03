"""What's new and notes to the developer."""
from datetime import datetime, timezone

from boredroom import news
from boredroom.models import Feedback, Person


def test_the_latest_release_is_news_until_read(db, seat):
    a = seat("trent")
    db.query(Person).filter_by(username="trent").update({"created_at": datetime(2026, 10, 1, tzinfo=timezone.utc)})
    db.commit()
    assert a.get("/me").json["news"]["id"] == news.LATEST.id
    page = a.get("/news").json
    assert [r["id"] for r in page["releases"]] == [r.id for r in news.RELEASES] and page["seen"] is None
    assert a.post("/news/seen", {"id": news.LATEST.id}).json["news"] is None
    assert a.post("/news/seen", {"id": news.RELEASES[-1].id}).json["news"] is None  # never moves back


def test_someone_new_never_gets_old_news(seat):
    assert seat("judy").get("/me").json["news"] is None  # joined after the latest release went out


def test_a_note_to_the_developer(db, seat):
    a = seat("trent")
    a.post("/boards", {"name": "soup"})
    assert a.post("/feedback", {"kind": "rant", "text": "x"}).status_code == 400
    assert a.post("/feedback", {"kind": "bug", "text": "   "}).status_code == 400
    r = a.post("/feedback", {"kind": "bug", "text": " the timer is off ", "board": "soup"})
    assert r.status_code == 201 and [(n["kind"], n["text"], n["board"]) for n in r.json] == [("bug", "the timer is off", "soup")]
    a.post("/feedback", {"kind": "idea", "text": "a dark mode for the grid", "board": "not-mine"})
    assert [n["board"] for n in a.get("/feedback").json] == [None, "soup"]  # a board you're not on isn't kept
    assert db.query(Feedback).first().release == news.LATEST.id
