from datetime import datetime, timezone

from boredroom import filing
from boredroom.models import GameRequest, PuzzleDay, Result

from .conftest import NOW

KRILL = "Krillion #107 🦐\n{}\n\n🐟🐟🏮🦑🐟🦑🫧"
WIKI = "Seawater ➡️ Babe Ruth ⏰ 02:09 🦶5 🔗 https://www.thewikigamedaily.com"
WIKI_ROUTE = ("Seawater ➡️ Babe Ruth ⏰ 02:10 🦶5 (Seawater ➡️ ASTM International ➡️ Babe Ruth) "
              "🔗 https://www.thewikigamedaily.com")


def kinds(f):
    return [e.kind for e in f.events]


def test_paste_files_and_repeats_merge(db, person):
    p = person("ivan")
    first = filing.file_paste(db, p, WIKI, now=NOW)
    assert kinds(first) == ["filed"]
    merged = filing.file_paste(db, p, WIKI_ROUTE, now=NOW)
    assert kinds(merged) == ["merged"] and merged.events[0].added == ["route"]
    assert kinds(filing.file_paste(db, p, WIKI, now=NOW)) == ["duplicate"]
    row = db.get(Result, first.events[0].result_id)
    assert row.metrics == {"steps": 5, "time": 129}
    assert [f["name"] for f in row.fields] == ["pages", "route"]
    assert len(row.paste_ids) == 3


def test_conflict_then_replace_marks_amended(db, person):
    p = person("ivan")
    first = filing.file_paste(db, p, KRILL.format(285), now=NOW)
    again = filing.file_paste(db, p, KRILL.format(510), now=NOW)
    assert kinds(again) == ["conflict"]
    rid = first.events[0].result_id
    assert db.get(Result, rid).metrics == {"score": 285}  # nothing changes until they answer
    row = filing.replace(db, p, rid, again.paste_id, now=NOW)
    assert row.metrics == {"score": 510} and row.amended_at is not None


def test_withdraw_then_refile(db, person):
    p = person("ivan")
    rid = filing.file_paste(db, p, KRILL.format(285), now=NOW).events[0].result_id
    assert filing.withdraw(db, p, rid, now=NOW).withdrawn_at is not None
    back = filing.file_paste(db, p, KRILL.format(300), now=NOW)
    assert kinds(back) == ["filed"] and back.events[0].result_id == rid
    row = db.get(Result, rid)
    assert row.withdrawn_at is None and row.amended_at is not None and row.metrics == {"score": 300}


def test_puzzle_days_late_and_not_out_yet(db, person):
    p = person("ivan")
    f = filing.file_paste(db, p, KRILL.format(1).replace("#107", "#105") + "\n\n"
                          + "www.maptap.gg October 30\n90🎯 90🎯 90🎯 90🎯 90🎯\nFinal score: 900", now=NOW)
    late, today = (db.get(Result, e.result_id) for e in f.events)
    assert (late.puzzle_day.isoformat(), late.late) == ("2026-10-28", True)
    assert (today.puzzle_key, today.puzzle_day.isoformat(), today.late) == ("2026-10-30", "2026-10-30", False)
    ahead = filing.file_paste(db, p, KRILL.format(1).replace("#107", "#110"), now=NOW)
    assert kinds(ahead) == ["not_out_yet"] and ahead.events[0].result_id is None


def test_a_page_pair_takes_the_day_of_its_first_filing(db, person):
    a = person("ivan")
    b = person("olv", tz="Asia/Singapore")
    filing.file_paste(db, a, WIKI, now=NOW)
    # filed by someone else two days later, it's still the same puzzle and day
    later = datetime(2026, 11, 1, 6, 0, tzinfo=timezone.utc)
    rid = filing.file_paste(db, b, WIKI, now=later).events[0].result_id
    assert db.get(Result, rid).puzzle_day.isoformat() == "2026-10-30"
    assert db.get(PuzzleDay, ("wiki", "seawater → babe ruth")).day.isoformat() == "2026-10-30"


def test_unknown_games_queue_a_request(db, person):
    p = person("ivan")
    f = filing.file_paste(db, p, "Perceptle2 #12 — 7/10\n🟩🟩🟥🟩🟩\nhttps://perceptle2.example", now=NOW)
    assert f.events == [] and f.unknown[0]["score"] == "7/10"
    db.commit()
    assert db.query(GameRequest).one().name == "Perceptle2"


def test_paste_endpoint(seat):
    a = seat("ivan")
    r = a.post("/pastes", {"text": WIKI})
    assert r.status_code == 201 and r.json["events"][0]["kind"] == "filed"
    assert a.post("/pastes", {"text": "  "}).status_code == 400
    mine = a.get("/results").json
    assert [(x["game"], x["metrics"]["steps"]) for x in mine] == [("wiki", 5)]

    conflict = a.post("/pastes", {"text": WIKI.replace("02:09 🦶5", "01:40 🦶4")}).json
    assert conflict["events"][0]["kind"] == "conflict"
    rid = conflict["events"][0]["result_id"]
    replaced = a.post(f"/results/{rid}/replace", {"paste_id": conflict["paste_id"]}).json
    assert replaced["metrics"]["steps"] == 4 and replaced["amended_at"]
    assert a.delete(f"/results/{rid}").json["withdrawn"] is True


def test_you_cant_touch_someone_elses_result(seat):
    a, b = seat("ivan"), seat("judy")
    rid = a.post("/pastes", {"text": WIKI}).json["events"][0]["result_id"]
    assert b.delete(f"/results/{rid}").status_code == 404
    pid = b.post("/pastes", {"text": WIKI}).json["paste_id"]
    assert a.post(f"/results/{rid}/replace", {"paste_id": pid}).status_code == 404


def test_a_preview_shows_what_filing_would_do_and_keeps_nothing(db, seat):
    a = seat("ivan")
    pre = a.post("/pastes/preview", {"text": WIKI}).json
    ev = pre["events"][0]
    assert (ev["kind"], ev["result_id"], ev["metrics"]) == ("filed", None, {"steps": 5, "time": 129})
    assert pre["paste_id"] is None
    assert db.query(Result).count() == 0 and a.get("/results").json == []
    assert a.post("/pastes", {"text": WIKI}).status_code == 201
    assert a.post("/pastes/preview", {"text": WIKI}).json["events"][0]["kind"] == "duplicate"
    assert db.query(Result).count() == 1
