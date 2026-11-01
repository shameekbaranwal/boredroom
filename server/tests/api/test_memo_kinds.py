"""The second batch of memos: the gossip beyond records and tenures."""
from datetime import date, datetime, timedelta

import pytest

from boredroom import memos
from boredroom.models import Memo
from boredroom.parser import REGISTRY

from .test_memos import IST, OCT30, board, file, krillion, noon, run


@pytest.fixture(autouse=True)
def clock(app):
    app.config["CLOCK"] = lambda: noon(OCT30)


def ago(n: int) -> date:
    return OCT30 - timedelta(days=n)


def wordle3(d: date, top: str = "⬛") -> str:
    """A three-row wordle in 3, drawn in dark (⬛) or light (⬜) mode."""
    return f"Wordle {1959 + (d - OCT30).days:,} 3/6\n\n{top * 3}🟩{top}\n🟨🟩{top}🟩🟩\n🟩🟩🟩🟩🟩"


def wordle(d: date, n: int) -> str:
    return f"Wordle {1959 + (d - OCT30).days:,} {n}/6\n\n⬛⬛🟩⬛🟩\n🟩🟩🟩🟩🟩"


def globle(d: date, n: int) -> str:
    return f"🌎 {d:%b} {d.day}, {d.year} 🌍\n🔥 1 | Avg. Guesses: 5\n{'🟧' * (n - 1)}🟩 = {n}\n\nhttps://globle-game.com"


def historydle(d: date, n: int) -> str:
    rows = "\n".join(["⬛🟩⬛⬛⬛"] * (n - 1) + ["🟩🟩🟩🟩🟩"])
    return f"Historydle #{REGISTRY['historydle'].current(noon(d), 'Asia/Kolkata')} - Classic\n\n{rows}"


def texts(seat, day=OCT30):
    return [m["text"] for m in seat.get(f"/boards/soup/meeting?day={day}").json["memos"]]


def test_a_jinx_is_the_same_grid_in_either_palette(db, seat):
    (trent, judy, mallory), p, b = board(db, seat, "trent", "judy", "mallory", games=("wordle",))
    file(db, p["trent"], wordle3(ago(1)), ago(1))
    file(db, p["judy"], wordle3(ago(1), "⬜"), ago(1))  # light mode, same squares
    file(db, p["mallory"], wordle(ago(1), 4), ago(1))
    run(db, b, p["trent"], OCT30)
    assert "jinx: judy and you filed the same wordle grid, square for square. compliance has been notified." in texts(trent)


def test_unanimous_replaces_the_photo_finish(db, seat):
    seats, p, b = board(db, seat, "trent", "judy", "mallory", "niaj", games=("krillion",))
    for n in p:
        file(db, p[n], krillion(ago(1), 300), ago(1))
    got = run(db, b, p["trent"], OCT30)
    assert f"unanimous:krillion:{ago(1)}" in got and not [k for k in got if k.startswith("photo")]
    assert "unanimous on krillion: all 4 present tied for #1. motion carried." in texts(seats[0])


def test_a_bull_run_then_a_coup(db, seat):
    (trent, judy, mallory), p, b = board(db, seat, "trent", "judy", "mallory", games=("krillion",))
    for k in range(5, 1, -1):  # trent wins four in a row, up to two days ago
        for n, score in (("trent", 400), ("judy", 300), ("mallory", 200)):
            file(db, p[n], krillion(ago(k), score), ago(k))
    for n, score in (("trent", 300), ("judy", 400), ("mallory", 200)):
        file(db, p[n], krillion(ago(1), score), ago(1))
    got = run(db, b, p["trent"], OCT30)
    assert got[f"run:krillion:{p['trent'].id}:{ago(2)}"].facts["n"] == 4
    assert "bull run: trent has won krillion 4 days running. the shareholders are delighted." in texts(judy, ago(1))
    assert "coup on krillion: judy ended your 4-day run. the board thanks you for your service." in texts(trent)
    assert "coup on krillion: you ended trent's 4-day run. the old guard is out." in texts(judy)


def test_a_clean_sweep(db, seat):
    games = ("wordle", "krillion", "globle", "historydle")
    seats, p, b = board(db, seat, "trent", "judy", "mallory", games=games)
    d = ago(1)
    for n, rank in (("trent", 0), ("judy", 1), ("mallory", 2)):
        file(db, p[n], wordle(d, 3 + rank), d)
        file(db, p[n], krillion(d, 400 - rank * 50), d)
        file(db, p[n], globle(d, 4 + rank), d)
        file(db, p[n], historydle(d, 2 + rank), d)
    got = run(db, b, p["judy"], OCT30)
    assert f"sweep:{p['trent'].id}:{d}" in got
    assert "clean sweep: #1 on all 4 of trent's items. the board demands a recount." in texts(seats[1])


def test_a_rumour_one_win_off_the_top(db, seat):
    (trent, judy, mallory), p, b = board(db, seat, "trent", "judy", "mallory", games=("krillion",))
    for k, winner in ((5, "judy"), (4, "judy"), (3, "judy"), (2, "trent"), (1, "trent")):
        for n in p:
            file(db, p[n], krillion(ago(k), 400 if n == winner else 300 if n != "mallory" else 100), ago(k))
    got = run(db, b, p["trent"], OCT30)
    assert f"rumour:{OCT30}:{p['trent'].id}>{p['judy'].id}" in got
    assert "rumour: you're one daily win off #1 this week. the board smells a takeover." in texts(trent)
    assert "rumour: trent is one daily win behind you this week. watch your back." in texts(judy)
    assert "rumour: trent is one daily win off judy's #1 this week. markets are jittery." in texts(mallory)


def test_the_closing_bell_and_the_night_shift(db, seat):
    (trent, judy), p, b = board(db, seat, "trent", "judy")
    from boredroom import filing
    # krillion's 29 oct puzzle closes at midnight in new york: 09:30 on the 30th here
    filing.file_paste(db, p["trent"], krillion(ago(1), 300), now=datetime(2026, 10, 30, 9, 26, tzinfo=IST))
    filing.file_paste(db, p["judy"], wordle(OCT30, 4), now=datetime(2026, 10, 30, 3, 12, tzinfo=IST))
    db.commit()
    run(db, b, p["trent"], OCT30)
    t = texts(trent)
    assert "closing bell: you filed krillion with 4 minutes to spare. the board respects the hustle." in t
    assert "night shift: judy filed wordle at 3:12am. the board does not pay overtime." in t


def test_a_milestone_only_when_it_is_news(db, seat, monkeypatch):
    monkeypatch.setattr(memos, "BOARD_COUNTS", (3, 5))
    (trent, judy), p, b = board(db, seat, "trent", "judy", games=("wordle",))
    for k in (12, 11, 10, 9):  # the 3rd result was long ago: no memo
        file(db, p["judy"], wordle(ago(k), 4), ago(k))
    file(db, p["trent"], wordle(OCT30, 4), OCT30)
    got = run(db, b, p["trent"], OCT30)
    assert [k for k in got if k.startswith("milestone")] == ["milestone:5"]
    assert "you filed the board's 5th result (wordle). the minutes are being bound in leather." in texts(trent)


def test_quorum_once_a_week(db, seat):
    seats, p, b = board(db, seat, "trent", "judy", "mallory", "niaj", "olivia", games=("krillion",))
    for k in (3, 2, 1):
        for i, n in enumerate(p):
            file(db, p[n], krillion(ago(k), 100 + 50 * i), ago(k))
    got = run(db, b, p["trent"], OCT30)
    assert [k for k in got if k.startswith("quorum")] == [f"quorum:{ago(2)}"]  # and not again the next day
    assert "quorum: all 5 active members filed. the motion to keep doing this carries." in texts(seats[0], ago(1))


def test_the_usual(db, seat):
    (trent, judy), p, b = board(db, seat, "trent", "judy", games=("wordle",))
    for k in range(4, -1, -1):
        file(db, p["judy"], wordle(ago(k), 4), ago(k))
    run(db, b, p["judy"], OCT30)
    assert "the usual: judy, same wordle score 5 days running. the board admires the consistency." in texts(trent)
    assert "the usual: same wordle score 5 days running. the board admires the consistency." in texts(judy)


def test_a_precedent_is_the_first_on_the_board(db, seat):
    (trent, judy), p, b = board(db, seat, "trent", "judy", games=("wordle",))
    for k in range(10, 0, -1):
        file(db, p["trent"], wordle(ago(k), 4), ago(k))
        file(db, p["judy"], wordle(ago(k), 5), ago(k))
    file(db, p["judy"], wordle(OCT30, 2), OCT30)
    got = run(db, b, p["judy"], OCT30)
    assert "precedent:wordle:in 2" in got and not [k for k in got if k.startswith("highlight")]
    assert "precedent on wordle: in 2 from judy, a first for the board. it will be cited." in texts(trent)


def test_a_record_says_whose_it_was(db, seat):
    (trent, judy), p, b = board(db, seat, "trent", "judy", games=("krillion",))
    file(db, p["judy"], krillion(ago(10), 400), ago(10))
    for k in range(9, 3, -1):
        file(db, p["trent"], krillion(ago(k), 300), ago(k))
        file(db, p["judy"], krillion(ago(k), 300), ago(k))
    file(db, p["trent"], krillion(OCT30, 450), OCT30)
    run(db, b, p["trent"], OCT30)
    assert "board record on krillion: you, taking it from judy after 10 days. it will be framed." in texts(trent)
    assert "board record on krillion: trent took yours, held 10 days. your frame is in storage." in texts(judy)


def test_board_member_of_the_month(db, seat, app):
    nov2 = date(2026, 11, 2)
    app.config["CLOCK"] = lambda: noon(nov2)
    (trent, judy), p, b = board(db, seat, "trent", "judy", games=("krillion",))
    for day in range(1, 32):
        d = date(2026, 10, day)
        file(db, p["trent"], krillion(d, 400 if day % 3 else 200), d)  # trent takes two days in three
        file(db, p["judy"], krillion(d, 300), d)
    got = run(db, b, p["trent"], nov2)
    assert got["commendation:2026-10"].subjects == [p["trent"].id]
    assert "board member of the month for october: trent, with a 68% win rate. a parking space has been reserved." in texts(judy, date(2026, 11, 1))


def test_small_talk_is_capped_at_three_a_day(db, seat):
    (trent, judy), p, b = board(db, seat, "trent", "judy", games=("wordle",))
    for i in range(3):
        db.add(Memo(board_id=b.id, key=f"usual:test:{i}", kind="usual", day=OCT30, subjects=[p["trent"].id], game_id="wordle",
                    facts={"on": str(OCT30), "n": 5, "metrics": {}, "outcome": "solved"}, interest=25, created_at=noon(OCT30)))
    db.commit()
    from boredroom import filing
    filing.file_paste(db, p["judy"], wordle(OCT30, 4), now=datetime(2026, 10, 30, 3, 12, tzinfo=IST))
    db.commit()
    assert not [k for k in run(db, b, p["judy"], OCT30) if k.startswith("night")]


def test_rivalry_of_the_week_on_mondays(db, seat, app):
    nov2 = date(2026, 11, 2)  # a monday
    app.config["CLOCK"] = lambda: noon(nov2)
    (trent, judy, mallory), p, b = board(db, seat, "trent", "judy", "mallory", games=("krillion",))
    for k in range(1, 13):  # twelve puzzles: trent 6, judy 5, one tie
        d = nov2 - timedelta(days=k)
        t, j = (400, 300) if k % 2 else (300, 400)
        file(db, p["trent"], krillion(d, 350 if k == 12 else t), d)
        file(db, p["judy"], krillion(d, 350 if k == 12 else j), d)
    got = run(db, b, p["trent"], nov2)
    assert got[f"rivalry:{nov2}:krillion:{p['trent'].id}:{p['judy'].id}"].facts == {
        "on": "2026-11-01", "w": 6, "l": 5, "n": 12}
    m = next(m for m in trent.get("/boards/soup/meeting?day=2026-11-02").json["memos"] if m["kind"] == "rivalry")
    assert m["text"] == "rivalry of the week, krillion: you lead judy 6–5 over the month. it's personal."
    assert m["link"] == "/b/soup/review?period=month&game=krillion&vs=judy"
    assert "rivalry of the week, krillion: trent leads you 6–5 over the month. it's personal." in texts(judy, nov2)
    assert "rivalry of the week, krillion: trent leads judy 6–5 over the month. it's personal." in texts(mallory, nov2)


def test_a_strong_quarter_and_never_a_weak_one(db, seat):
    (trent, judy), p, b = board(db, seat, "trent", "judy", games=("wordle",))
    for k in range(15, 0, -1):
        file(db, p["judy"], wordle(ago(k), 5 if k >= 8 else 3), ago(k))  # judy improves
        file(db, p["trent"], wordle(ago(k), 3 if k >= 8 else 5), ago(k))  # trent doesn't: no memo
    got = run(db, b, p["trent"], OCT30)
    assert [k for k in got if k.startswith("earnings")] == [f"earnings:wordle:{p['judy'].id}:{ago(2)}"]  # once a fortnight
    assert "strong quarter: judy's wordle average went from 5.0 to 3.3 this week. analysts are upgrading." in texts(trent, ago(1))


def test_perfect_attendance(db, seat):
    (trent, judy), p, b = board(db, seat, "trent", "judy", games=("wordle", "krillion", "globle"))
    for k in range(20, 0, -1):  # both file all three for 20 days, trent skips a globle 4 days ago
        for n in p:
            file(db, p[n], wordle(ago(k), 4), ago(k))
            file(db, p[n], krillion(ago(k), 300 if n == "judy" else 250 + k), ago(k))
            if n == "judy" or k != 4:
                file(db, p[n], globle(ago(k), 5), ago(k))
    got = run(db, b, p["judy"], OCT30)
    # games are regulars once filed on 10 of the 14 days before: from 10 days ago, so yesterday
    # is judy's 10th in a row (and 2 days ago her 9th, no memo); trent's run restarted after the skip
    assert [k for k in got if k.startswith("attendance")] == [f"attendance:{p['judy'].id}:{ago(1)}"]
    assert "perfect attendance: all of judy's regulars, 10 days running. hr is drafting a certificate." in texts(trent)
