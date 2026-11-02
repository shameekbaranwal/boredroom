"""Weekly games: a puzzle a week, filed once and done until it resets."""
from datetime import date, datetime, timedelta

import pytest

from boredroom import memos, reads
from boredroom.parser import REGISTRY

from .test_memos import IST, board, file, noon, run

MON = date(2026, 11, 2)  # travle challenge #144's week


@pytest.fixture(autouse=True)
def clock(app):
    app.config["CLOCK"] = lambda: noon(MON)


def challenge(d: date, over: int) -> str:
    return f"#travle_challenge #{144 + (d - MON).days // 7} +{over}\n🟩🟧✅🟩✅✅\nhttps://travle.earth/challenge"


def test_the_puzzle_lasts_the_week():
    g = REGISTRY["travle_challenge"]
    assert g.weekly() and not REGISTRY["travle"].weekly()
    for d in range(7):
        assert g.current(noon(MON + timedelta(days=d)), "Asia/Kolkata") == 144
        assert g.reset.game_day(noon(MON + timedelta(days=d)), "Asia/Kolkata") == MON
    assert g.current(noon(MON + timedelta(days=7)), "Asia/Kolkata") == 145
    assert g.puzzle_day(146) == MON + timedelta(days=14)


def test_filed_all_week_then_open_again(db, seat):
    _, p, b = board(db, seat, "trent", "judy", games=("travle_challenge", "wordle"))
    file(db, p["trent"], challenge(MON, 1), MON)
    item = lambda d: next(i for i in reads.today(db, b, p["trent"], noon(d))["items"] if i["game"] == "travle_challenge")  # noqa: E731
    thu = item(MON + timedelta(days=3))
    assert thu["filed"] and thu["weekly"] and thu["mine"]["puzzle"] == "144"
    assert thu["resets_at"] == datetime(2026, 11, 9, tzinfo=IST).isoformat()
    nxt = item(MON + timedelta(days=7))
    assert not nxt["filed"] and nxt["puzzle"] == "145"
    # its tenure counts weeks: filed last week, still alive (at risk) this week
    assert nxt["tenure"] == {"days": 1, "at_risk": True}
    file(db, p["trent"], challenge(MON + timedelta(days=7), 2), MON + timedelta(days=8))
    assert item(MON + timedelta(days=8))["tenure"] == {"days": 2, "at_risk": False}


def test_reviews_have_no_today_for_it(db, seat):
    _, p, b = board(db, seat, "trent", "judy", games=("travle_challenge", "wordle"))
    file(db, p["trent"], challenge(MON, 1), MON)
    file(db, p["judy"], challenge(MON, 3), MON + timedelta(days=2))
    wed = noon(MON + timedelta(days=2))
    today = reads.review(db, b, p["trent"], "today", now=wed)
    assert all(x["filed"] == 0 for x in today["standings"])  # the weekly game sits "today" out
    week = reads.review(db, b, p["trent"], "week", now=wed)
    assert {x["nickname"]: x["wins"] for x in week["standings"]} == {"trent": 1, "judy": 0}
    alone = reads.review(db, b, p["trent"], "today", game="travle_challenge", now=wed)
    assert alone["weekly"] and [x["nickname"] for x in alone["standings"]][:2] == ["trent", "judy"]
    assert alone["strip"][-1] == "on"  # alone, the strip counts weeks: this one, won


def test_the_week_has_a_champion_a_run_and_a_last_call(db, seat):
    _, p, b = board(db, seat, "trent", "judy", "mallory", games=("travle_challenge",))
    for w in range(4):
        d = MON + timedelta(days=7 * w)
        file(db, p["trent"], challenge(d, 0), d)
        file(db, p["judy"], challenge(d, 2), d + timedelta(days=1))
    sun = MON + timedelta(days=27)
    got = run(db, b, p["trent"], sun)
    last = got[f"lastcall:travle_challenge:{MON + timedelta(days=21)}"]
    assert memos.text(last, {}, None) == "last call: travle challenge closes tonight. 2 of 3 in."
    champ = got[f"champion:travle_challenge:{MON + timedelta(days=7)}"]
    nick = {p[n].id: n for n in p}
    assert memos.text(champ, nick, None) == "travle challenge #145 goes to trent, best of 2 this week. 2 weeks running."
    assert champ.day == MON + timedelta(days=14)
    fixture = got[f"fixture:travle_challenge:{p['trent'].id}:{MON + timedelta(days=21)}"]
    assert memos.text(fixture, nick, p["trent"].id) == "your 4-week run on travle challenge. a standing appointment."
    # the daily rules leave it alone: no daily wins, tenures in days or the like
    assert {m.kind for m in got.values()} <= {"champion", "fixture", "lastcall"}
