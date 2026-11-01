from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text

from boredroom import filing, reminders
from boredroom.app import create_app
from boredroom.config import Config
from boredroom.db import Base
from boredroom.models import Person, PushLog, PushSubscription
from boredroom.parser import REGISTRY

from .conftest import Seat

CFG = replace(Config(), vapid_public_key="BPub", vapid_private_key="priv", scheduler=False)
SUB = {"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "keys": {"p256dh": "BKey", "auth": "auth"}}
# krillion resets at midnight in new york: 09:30 IST until 1 nov 2026, 10:30 after
IST = timezone(timedelta(hours=5, minutes=30))


def krillion(now):
    return f"Krillion #{REGISTRY['krillion'].current(now, 'Asia/Kolkata')} 🦐\n340\n\n🐟🐟🦑🐟🦑🐟🐟"


@pytest.fixture
def push_app(engine):
    app = create_app(CFG, engine=engine)
    app.config["PUSH_SENDER"] = Fake()
    yield app
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as c:
        c.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


class Fake:
    """A push service: records what was sent, answers with `status`."""
    def __init__(self, status=201):
        self.status, self.sent = status, []

    def __call__(self, sub, push, cfg):
        self.sent.append((sub.endpoint, push))
        return self.status


@pytest.fixture
def s(push_app):
    from sqlalchemy.orm import Session
    with Session(push_app.extensions["boredroom.engine"], expire_on_commit=False) as s:
        yield s


def board(push_app, *names):
    c = push_app.test_client()
    seats = [Seat(c, n) for n in names]
    code = seats[0].post("/boards", {"name": "soup"}).json["invite"]["code"]
    for x in seats[1:]:
        x.post("/boards/join", {"code": code})
    for x in seats:
        x.put("/boards/soup/agenda/krillion")
        x.put("/boards/soup/agenda/wordle")
    return seats


def test_devices_subscribe_once_and_move_between_people(push_app):
    trent, judy = board(push_app, "trent", "judy")
    assert trent.get("/me/push").json == {"available": True, "devices": []}
    for _ in range(2):
        r = trent.client.put("/api/v1/me/push", json=SUB, headers=trent.headers | {"User-Agent": "Mozilla/5.0 (Linux; Android 14) Chrome/130"})
        assert r.status_code == 200
    assert [d["device"] for d in r.json["devices"]] == ["android · chrome"]
    # the same phone, now someone else's
    judy.put("/me/push", SUB)
    assert trent.get("/me/push").json["devices"] == []
    sid = judy.get("/me/push").json["devices"][0]["id"]
    assert trent.delete(f"/me/push/{sid}").status_code == 404
    assert judy.delete(f"/me/push/{sid}").json["devices"] == []
    assert trent.put("/me/push", {"endpoint": "http://evil/x", "keys": SUB["keys"]}).status_code == 400


def test_config_offers_the_key_only_when_push_is_set_up(push_app, client):
    assert push_app.test_client().get("/api/v1/config").json["vapid_public_key"] == "BPub"
    assert client.get("/api/v1/config").json["vapid_public_key"] is None
    trent = Seat(client, "trent")
    assert trent.put("/me/push", SUB).status_code == 503


def test_test_push_reaches_every_device_and_drops_dead_ones(push_app, s):
    (trent,) = board(push_app, "trent")
    trent.put("/me/push", SUB)
    trent.put("/me/push", {**SUB, "endpoint": "https://web.push.apple.com/xyz"})
    r = trent.post("/me/push/test")
    assert r.json["sent"] == 2 and "test memo" in push_app.config["PUSH_SENDER"].sent[0][1].title
    push_app.config["PUSH_SENDER"].status = 410
    assert trent.post("/me/push/test").json == {"sent": 0, "devices": []}


def test_digest_and_nudge_switches(push_app):
    (trent,) = board(push_app, "trent")
    b = trent.get("/boards/soup").json
    assert b["you"]["digest"] is True and b["you"]["nudges"] == []
    assert trent.patch("/boards/soup/me", {"digest": False}).json["you"]["digest"] is False
    assert trent.put("/boards/soup/agenda/krillion/nudge").json["you"]["nudges"] == ["krillion"]
    assert trent.put("/boards/soup/agenda/anno/nudge").status_code == 409
    assert trent.delete("/boards/soup/agenda/krillion/nudge").json["you"]["nudges"] == []
    assert trent.patch("/boards/soup/me", {"nickname": "t"}).json["you"]["nickname"] == "t"


def _setup(push_app, s, *names):
    seats = board(push_app, *names)
    for x in seats:
        x.put("/me/push", {**SUB, "endpoint": f"{SUB['endpoint']}-{x.name}"})
    return seats, {n: s.scalar(select(Person).where(Person.username == n)) for n in names}


def test_a_nudge_goes_an_hour_before_reset_once(push_app, s):
    (trent,), _ = _setup(push_app, s, "trent")
    trent.put("/boards/soup/agenda/krillion/nudge")
    fake = Fake()
    early = datetime(2026, 11, 1, 8, 0, tzinfo=IST)  # 1h30 before krillion's 09:30
    assert reminders.tick(s, CFG, early, fake) == 0
    at = datetime(2026, 11, 1, 8, 31, tzinfo=IST)
    assert reminders.tick(s, CFG, at, fake) == 1
    assert fake.sent[0][1].title == "krillion resets in 59m"
    assert fake.sent[0][1].url == "/b/soup"
    assert reminders.tick(s, CFG, at + timedelta(minutes=1), fake) == 1 - 1  # logged: never twice
    assert len(fake.sent) == 1
    assert s.scalar(select(PushLog.status)) == "sent"


def test_filed_games_and_switched_off_ones_stay_quiet(push_app, s):
    (trent,), people = _setup(push_app, s, "trent")
    at = datetime(2026, 11, 1, 8, 45, tzinfo=IST)
    fake = Fake()
    assert reminders.tick(s, CFG, at, fake) == 0  # nudges are off by default
    trent.put("/boards/soup/agenda/krillion/nudge")
    filing.file_paste(s, people["trent"], krillion(at), now=at)
    s.commit()
    assert reminders.tick(s, CFG, at, fake) == 0


def test_games_resetting_close_together_share_a_push(push_app, s):
    (trent,), people = _setup(push_app, s, "trent")
    for gm in ("krillion", "anno"):  # 09:30 and 10:30 ist
        trent.put(f"/boards/soup/agenda/{gm}")
        trent.put(f"/boards/soup/agenda/{gm}/nudge")
    fake = Fake()
    reminders.tick(s, CFG, datetime(2026, 11, 1, 8, 30, tzinfo=IST), fake)
    assert len(fake.sent) == 1
    title = fake.sent[0][1].title
    # anno resets at 10:30, an hour after krillion: it gets its own push later
    assert title == "krillion resets in 1h"
    reminders.tick(s, CFG, datetime(2026, 11, 1, 9, 30, tzinfo=IST), fake)
    assert [p.title for _, p in fake.sent] == ["krillion resets in 1h", "anno resets in 1h"]


def test_tenure_at_risk_is_mentioned(push_app, s):
    (trent,), people = _setup(push_app, s, "trent")
    trent.put("/boards/soup/agenda/krillion/nudge")
    for day in (30, 31):
        at = datetime(2026, 10, day, 8, 0, tzinfo=IST)  # before that day's 09:30 reset
        filing.file_paste(s, people["trent"], krillion(at), now=at)
    s.commit()
    fake = Fake()
    reminders.tick(s, CFG, datetime(2026, 11, 1, 8, 40, tzinfo=IST), fake)
    assert fake.sent[0][1].body == "your 2-day tenure lapses at reset."


def test_the_evening_digest(push_app, s):
    (trent, judy, mallory), people = _setup(push_app, s, "trent", "judy", "mallory")
    at = datetime(2026, 11, 1, 20, 0, 30, tzinfo=IST)
    # krillion's 1 nov puzzle runs until 10:30 on the 2nd
    filing.file_paste(s, people["judy"], krillion(at), now=at)
    filing.file_paste(s, people["mallory"], krillion(at), now=at)
    s.commit()
    judy.patch("/boards/soup/me", {"digest": False})
    fake = Fake()
    assert reminders.tick(s, CFG, datetime(2026, 11, 1, 19, 59, tzinfo=IST), fake) == 0
    reminders.tick(s, CFG, at, fake)
    got = {ep.rsplit("-", 1)[1]: p for ep, p in fake.sent}
    assert set(got) == {"trent", "mallory"}  # judy switched hers off
    assert got["trent"].title == "soup: the meeting started without you."
    assert got["trent"].body == "judy and mallory filed 2 between them. open: wordle, krillion. wordle resets in 4h."
    assert got["mallory"].title == "soup: 1 item still open."
    assert reminders.tick(s, CFG, at + timedelta(minutes=5), fake) == 0  # once a day


def test_nothing_open_means_no_digest(push_app, s):
    (trent,), people = _setup(push_app, s, "trent")
    trent.delete("/boards/soup/agenda/wordle")
    at = datetime(2026, 11, 1, 20, 10, tzinfo=IST)
    filing.file_paste(s, people["trent"], krillion(at), now=at)
    s.commit()
    fake = Fake()
    assert reminders.tick(s, CFG, at, fake) == 0
    assert s.scalar(select(PushLog.status)) == "skipped"


def test_a_device_that_keeps_failing_is_dropped(push_app, s):
    (trent,), people = _setup(push_app, s, "trent")
    trent.put("/boards/soup/agenda/krillion/nudge")
    fake = Fake(status=500)
    for day in (2, 3, 4):
        reminders.tick(s, CFG, datetime(2026, 11, day, 9, 45, tzinfo=IST), fake)
    assert s.scalar(select(PushSubscription)) is None
    assert set(s.scalars(select(PushLog.status))) == {"failed"}


def test_health_reports_the_scheduler(push_app, s):
    assert not reminders.healthy(s)
    reminders.tick(s, CFG, datetime.now(timezone.utc), Fake())
    assert reminders.healthy(s)


def test_the_service_worker_renews_a_replaced_subscription(push_app):
    (trent,) = board(push_app, "trent")
    trent.put("/me/push", SUB)
    c = push_app.test_client()
    new = {**SUB, "endpoint": "https://fcm.googleapis.com/fcm/send/def"}
    assert c.post("/api/v1/me/push/renew", json={"old": "https://nope/x", "sub": new}).status_code == 404
    assert c.post("/api/v1/me/push/renew", json={"old": SUB["endpoint"], "sub": new}).status_code == 200
    assert [d["endpoint"] for d in trent.get("/me/push").json["devices"]] == [new["endpoint"]]
