from datetime import date, datetime, timezone

from boredroom.parser import REGISTRY, forward_text, rank
from boredroom.parser.text import duration, emoji_cells, nearest_year, normalise, number

from ..conftest import one

KRILL = "Krillion #107 🦐\n{score}\n\n🐟🐟🏮🦑🐟🦑🫧"


def test_normalise_strips_invisible_edited_wrappers_and_tracking():
    raw = ("[Daily WIKI SPOILER]\n\n​​hi <This message was edited>\n"
           "<https://fermi.gg/s/daily>\nhttps://playpindrop.app?r=abc\n"
           "https://DailyOrbs.com/2026-10-11?utm_source=share&keep=1")
    assert normalise(raw) == ("hi\nhttps://fermi.gg/s/daily\nhttps://playpindrop.app\n"
                              "https://DailyOrbs.com/2026-10-11?keep=1")


def test_helpers():
    assert number("195,288,089") == 195288089 and number("1.20") == 1.2
    assert duration("02:09") == 129 and duration("1m 7s") == 67 and duration("45s") == 45
    assert nearest_year(12, 31, date(2027, 1, 2)) == date(2026, 12, 31)
    assert nearest_year(1, 1, date(2026, 12, 31)) == date(2027, 1, 1)  # one day ahead is fine
    assert emoji_cells("⚪️🟣 🟣") == ["⚪", "🟣", "🟣"]


def test_comment_after_result_and_before_it(p):
    r = one(p("yesterday's\n" + KRILL.format(score=305) + "\n\ni couldn't think of anything"))
    assert r.metrics == {"score": 305}
    assert r.comment == "yesterday's\ni couldn't think of anything"


def test_several_results_in_one_paste(p):
    text = KRILL.format(score=305) + "\n" + "www.maptap.gg October 30\n90🎯 90🎯 90🎯 90🎯 90🎯\nFinal score: 900"
    got = p(text)
    assert [r.game for r in got.results] == ["krillion", "maptap"]
    assert got.results[0].comment == ""


def test_plain_chat_is_not_a_result(p):
    got = p("Connections today has jojo ref")
    assert not got.results and not got.unknown and got.note


def test_unknown_game_prefill(p):
    got = p("PetGuessrX #106 — 5/10\n🐱🐶🐱🐶❌\nhttps://petguessrx.com")
    assert not got.results
    u = got.unknown[0]
    assert (u.name, u.link, u.puzzle, u.score) == ("PetGuessrX", "petguessrx.com", "106", "5/10")


def test_status_current_late_ahead(p):
    assert one(p(KRILL.format(score=1).replace("#107", "#105"))).status == "late"
    assert one(p(KRILL.format(score=1))).status == "current"
    ahead = one(p(KRILL.format(score=1).replace("#107", "#109")))
    assert ahead.status == "ahead" and ahead.warnings


def test_reset_is_per_game():
    # 9:00 IST on 30 Oct: krillion (resets 9:30 IST) is still on yesterday's puzzle
    early = datetime(2026, 10, 30, 3, 30, tzinfo=timezone.utc)
    assert REGISTRY["krillion"].current(early, "Asia/Kolkata") == 106
    assert REGISTRY["maptap"].current(early, "Asia/Kolkata") == date(2026, 10, 30)
    # 3:00 IST on 31 Oct, before utc midnight: maptap and pindrop are already on the 31st's
    night = datetime(2026, 10, 30, 21, 30, tzinfo=timezone.utc)
    assert REGISTRY["maptap"].current(night, "Asia/Kolkata") == date(2026, 10, 31)
    assert REGISTRY["pindrop"].current(night, "Asia/Kolkata") == 242
    assert REGISTRY["fermi"].current(night, "Asia/Kolkata") == REGISTRY["fermi"].current(early, "Asia/Kolkata")


def test_out_of_range_is_partial(p):
    r = one(p(KRILL.format(score=900)))
    assert r.confidence == "partial"


def test_rank_ties_share_a_place_and_fails_go_last(p):
    rs = [one(p(KRILL.format(score=s))) for s in (340, 455, 340, 305)]
    assert [(pl, r.metrics["score"]) for pl, r in rank(rs)] == [(1, 455), (2, 340), (2, 340), (4, 305)]
    conn = "Connections\nPuzzle #1237\n" + "{}\n🟨🟨🟨🟨\n🟩🟩🟩🟩\n🟦🟦🟦🟦\n🟪🟪🟪🟪"
    clean = one(p(conn.format("🟨🟨🟨🟨").replace("🟨🟨🟨🟨\n🟨", "🟨", 1)))
    failed = one(p("Connections\nPuzzle #1237\n🟨🟩🟨🟨\n🟨🟩🟨🟨\n🟨🟨🟨🟩\n🟨🟨🟨🟨\n🟦🟦🟩🟦"))
    assert [r.outcome for _, r in rank([failed, clean])] == ["solved", "failed"]


def test_rank_skips_metric_one_side_lacks(p):
    a, b = one(p(KRILL.format(score=300))), one(p(KRILL.format(score=300)))
    a.metrics["extra"] = 1
    assert rank([a, b])[1][0] == 1


def test_forward_wraps_spoilers(p):
    wiki = one(p("A ➡️ B ⏰ 01:00 🦶2 (A ➡️ C ➡️ B) 🔗 https://www.thewikigamedaily.com"))
    out = forward_text(wiki)
    assert out.startswith("[wiki game spoiler]") and "​" * 100 in out
    assert forward_text(one(p(KRILL.format(score=1)))) == KRILL.format(score=1)
