from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from boredroom import filing, memos
from boredroom.models import Board, Memo, Person

IST = timezone(timedelta(hours=5, minutes=30))
OCT30 = date(2026, 10, 30)


@pytest.fixture(autouse=True)
def clock(app):
    app.config["CLOCK"] = lambda: noon(OCT30)


def noon(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 12, 0, tzinfo=IST)


def krillion(d: date, score: int) -> str:
    return f"Krillion #{107 + (d - OCT30).days} 🦐\n{score}\n\n🐟🐟🏮🦑🐟🦑🫧"


def wordle(d: date, guesses: int | str) -> str:
    return f"Wordle {1959 + (d - OCT30).days:,} {guesses}/6\n\n⬛⬛🟩⬛🟩\n🟩🟩🟩🟩🟩"


def board(db, seat, *names, games=("krillion", "wordle")):
    seats = [seat(n) for n in names]
    code = seats[0].post("/boards", {"name": "soup"}).json["invite"]["code"]
    for x in seats[1:]:
        x.post("/boards/join", {"code": code})
    for x in seats:
        for gm in games:
            x.put(f"/boards/soup/agenda/{gm}")
    people = {n: db.scalar(select(Person).where(Person.username == n)) for n in names}
    return seats, people, db.query(Board).one()


def file(db, person, text, d):
    filing.file_paste(db, person, text, now=noon(d))
    db.commit()


def run(db, b, viewer, d):
    db.expire_all()
    memos.refresh(db, b, viewer, now=noon(d))
    db.commit()
    return {m.key: m for m in db.scalars(select(Memo))}


def test_a_board_record_and_a_personal_best(db, seat):
    (trent, judy), p, b = board(db, seat, "trent", "judy")
    start = OCT30 - timedelta(days=6)
    for k in range(6):  # 12 results, best 300
        d = start + timedelta(days=k)
        file(db, p["trent"], krillion(d, 200 + k * 10), d)
        file(db, p["judy"], krillion(d, 250 + k * 10), d)
    file(db, p["judy"], krillion(OCT30, 400), OCT30)
    file(db, p["trent"], krillion(OCT30, 260), OCT30)  # beats his own 250
    got = run(db, b, p["trent"], OCT30)
    assert set(got) >= {f"record:krillion:{OCT30}", f"pb:krillion:{p['trent'].id}:{OCT30}"}
    assert f"pb:krillion:{p['judy'].id}:{OCT30}" not in got  # the record says it already
    a = trent.get("/boards/soup/today").json["memos"]
    assert [m["text"] for m in a] == ["board record on krillion: judy. it will be framed.", "you set a personal best on krillion."]
    assert a[0]["score"] == {"metrics": {"score": 400}, "outcome": "solved"}
    assert a[0]["link"] == "/b/soup/review?period=all&game=krillion"
    # filed again later: nothing new, nothing rewritten
    assert memos.refresh(db, b, p["trent"], now=noon(OCT30) + timedelta(hours=2)) == 0


def test_hostile_takeover_over_the_rolling_week(db, seat):
    (trent, judy), p, b = board(db, seat, "trent", "judy")
    d1, d2, d3 = OCT30 - timedelta(days=2), OCT30 - timedelta(days=1), OCT30
    file(db, p["trent"], krillion(d1, 300), d1)
    file(db, p["judy"], krillion(d1, 200), d1)
    for gm, mine, theirs in ((krillion, 200, 300), (wordle, 5, 3)):
        file(db, p["trent"], gm(d2, mine), d2)
        file(db, p["judy"], gm(d2, theirs), d2)
    got = run(db, b, p["trent"], d3)
    (key,) = [k for k in got if k.startswith("takeover")]
    assert key == f"takeover:{d3}:{p['judy'].id}>{p['trent'].id}"
    you = trent.get("/boards/soup/today").json["memos"]
    assert you[0]["text"] == "hostile takeover: judy passed you for #1 this week." and you[0]["number"] == "2–1"
    assert judy.get("/boards/soup/today").json["memos"][0]["text"] == "you took #1 from trent this week. the board is reorganising."


def test_closings_photo_finish_comeback_and_a_tough_room(db, seat):
    seats, p, b = board(db, seat, "trent", "judy", "mallory")
    d1, d2 = OCT30 - timedelta(days=2), OCT30 - timedelta(days=1)
    for n, s1, s2 in (("trent", 300, 300), ("judy", 200, 300), ("mallory", 100, 400)):
        file(db, p[n], krillion(d1, s1), d1)
        file(db, p[n], krillion(d2, s2), d2)
    for n in ("trent", "judy"):
        file(db, p[n], wordle(d2, "X"), d2)
    got = run(db, b, p["trent"], OCT30)
    assert f"comeback:krillion:{p['mallory'].id}:{d2}" in got
    assert got[f"missed:wordle:{d2}"].facts["n"] == 2 and got[f"missed:wordle:{d2}"].day == OCT30
    meet = seats[0].get(f"/boards/soup/meeting?day={OCT30}").json
    texts = [m["text"] for m in meet["memos"]]
    assert "comeback on krillion: mallory, last the day before, first this time." in texts
    assert "2 members missed target on wordle. a tough room." in texts
    assert not [k for k in got if k.startswith("photo")]  # two failed wordles aren't a tie for #1


def test_photo_finish_names_you_last(db, seat):
    (trent, judy), p, b = board(db, seat, "trent", "judy")
    d = OCT30 - timedelta(days=1)
    for n in ("trent", "judy"):
        file(db, p[n], krillion(d, 300), d)
    run(db, b, p["trent"], OCT30)
    (m,) = trent.get("/boards/soup/meeting").json["memos"]
    assert m["text"] == "photo finish on krillion: judy and you. the chair abstains."
    assert m["plain"] == "photo finish on krillion: judy and trent. the chair abstains."


def test_tenure_milestones_and_endings(db, seat):
    (trent, judy), p, b = board(db, seat, "trent", "judy", games=("wordle",))
    for k in range(8, 1, -1):  # trent: 7 days up to 2 days ago, then nothing
        d = OCT30 - timedelta(days=k)
        file(db, p["trent"], wordle(d, 4), d)
    for k in range(6, -1, -1):  # judy: 7 days ending today
        d = OCT30 - timedelta(days=k)
        file(db, p["judy"], wordle(d, 4), d)
    got = run(db, b, p["judy"], OCT30)
    gap = OCT30 - timedelta(days=1)
    ended = got[f"ended:wordle:{p['trent'].id}:{OCT30 - timedelta(days=2)}"]
    assert ended.facts["n"] == 7 and ended.day == OCT30  # reported once the missed puzzle closed
    assert f"tenure:wordle:{p['judy'].id}:{OCT30}" in got
    t = judy.get("/boards/soup/today").json["memos"]
    assert "your 7-day tenure on wordle. the board notes the commitment." in [m["text"] for m in t]
    # a late filing of the missing day revives the tenure: the memo goes quiet
    file(db, p["trent"], wordle(gap, 4), OCT30)
    m = trent.get(f"/boards/soup/meeting?day={OCT30}").json["memos"]
    assert not [x for x in m if x["kind"] == "ended"]


def test_dismissing_hides_it_from_the_agenda_not_the_meeting(db, seat):
    (trent, judy), p, b = board(db, seat, "trent", "judy", games=("wordle",))
    for k in range(6, -1, -1):
        d = OCT30 - timedelta(days=k)
        file(db, p["judy"], wordle(d, 4), d)
    run(db, b, p["judy"], OCT30)
    (m,) = trent.get("/boards/soup/today").json["memos"]
    assert trent.post(f"/boards/soup/memos/{m['id']}/dismiss").json["memos"] == []
    assert trent.get("/boards/soup/today").json["memos"] == []
    assert judy.get("/boards/soup/today").json["memos"][0]["id"] == m["id"]  # only for trent
    meet = trent.get(f"/boards/soup/meeting?day={OCT30}").json
    assert meet["memos"][0]["dismissed"] is True
    trent.delete(f"/boards/soup/memos/{m['id']}/dismiss")
    assert trent.get("/boards/soup/today").json["memos"][0]["id"] == m["id"]
    assert trent.post("/boards/soup/memos/999/dismiss").status_code == 404
    assert trent.get("/boards/soup/meeting?day=nope").status_code == 400


def test_the_agenda_keeps_one_per_kind(db, seat):
    seats, p, b = board(db, seat, "trent", "judy", "mallory", "niaj", games=("wordle", "krillion"))
    for n in p:
        for k in range(6, -1, -1):
            d = OCT30 - timedelta(days=k)
            file(db, p[n], wordle(d, 4), d)
            file(db, p[n], krillion(d, 300), d)
    run(db, b, p["trent"], OCT30)
    # eight 7-day tenures: the agenda carries one, yours; the meeting has them all
    (a,) = seats[0].get("/boards/soup/today").json["memos"]
    assert a["kind"] == "tenure" and a["me"]
    meet = seats[0].get("/boards/soup/meeting").json["memos"]
    assert sum(m["kind"] == "tenure" for m in meet) == 8


def test_only_the_last_two_days_are_read(db, seat):
    (trent, judy), p, b = board(db, seat, "trent", "judy", games=("wordle",))
    old = OCT30 - timedelta(days=20)
    for k in range(7):
        d = old + timedelta(days=k)
        file(db, p["judy"], wordle(d, 4), d)
    assert run(db, b, p["judy"], OCT30) == {}


def test_a_pip_goes_to_the_week_s_last_once(db, seat):
    seats, p, b = board(db, seat, "trent", "judy", "niaj", "mallory")
    for k in range(10, 0, -1):
        d = OCT30 - timedelta(days=k)
        for n, score, guesses in (("trent", 400, 5), ("judy", 400, 5), ("niaj", 100, 2), ("mallory", 100, 5)):
            file(db, p[n], krillion(d, score), d)
            file(db, p[n], wordle(d, guesses), d)
    got = run(db, b, p["trent"], OCT30)
    pips = [k for k in got if k.startswith("pip")]
    assert pips == [f"pip:{p['mallory'].id}:{OCT30 - timedelta(days=1)}"]  # and not again the next day
    m = seats[3].get(f"/boards/soup/meeting?day={OCT30 - timedelta(days=1)}").json["memos"]
    assert "you're on a pip. the board believes in you, mostly." in [x["text"] for x in m]
    assert not [x for x in seats[3].get("/boards/soup/today").json["memos"] if x["kind"] == "pip"]  # never on the agenda


def test_a_highlight_says_how_often_lately(db, seat):
    (trent, judy), p, b = board(db, seat, "trent", "judy", games=("wordle",))
    for k in (3, 0):
        d = OCT30 - timedelta(days=k)
        file(db, p["judy"], "Connections\nPuzzle #{}\n🟪🟪🟪🟪\n🟦🟦🟦🟦\n🟩🟩🟩🟩\n🟨🟨🟨🟨".format(1237 + (d - OCT30).days), d)
    trent.put("/boards/soup/agenda/connections")
    judy.put("/boards/soup/agenda/connections")
    run(db, b, p["judy"], OCT30)
    texts = [m["text"] for m in trent.get("/boards/soup/meeting").json["memos"]]
    assert any(t.startswith("connections: ") and t.endswith("from judy. that's 2 in a week.") for t in texts), texts
