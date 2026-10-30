from boredroom.parser import merge

from .conftest import one

PLAIN = "Seawater ➡️ Babe Ruth ⏰ 02:09 🦶5 🔗 https://www.thewikigamedaily.com"
ROUTE = ("Seawater ➡️ Babe Ruth ⏰ 02:10 🦶5 (Seawater ➡️ ASTM International ➡️ "
         "West Conshohocken, Pennsylvania ➡️ Philadelphia ➡️ Major League Baseball ➡️ Babe Ruth) "
         "🔗 https://www.thewikigamedaily.com")


def test_route_added_later_merges(p):
    m = merge(one(p(PLAIN)), one(p(ROUTE)))
    assert m.kind == "enrich" and m.added == ["route"]
    assert m.result.metrics == {"steps": 5, "time": 129}  # the score already seen stays
    assert m.result.field_value("route")[1] == "ASTM International"
    assert "ASTM" in m.result.raw  # forwards the richer text


def test_route_first_then_plain_is_a_duplicate(p):
    assert merge(one(p(ROUTE)), one(p(PLAIN))).kind == "duplicate"


def test_same_paste_twice_is_a_duplicate(p):
    assert merge(one(p(PLAIN)), one(p(PLAIN))).kind == "duplicate"


def test_a_redo_is_a_conflict(p):
    redo = PLAIN.replace("02:09 🦶5", "01:40 🦶4")
    assert merge(one(p(PLAIN)), one(p(redo))).kind == "conflict"


def test_time_beyond_tolerance_is_a_conflict(p):
    later = ROUTE.replace("02:10", "02:40")
    assert merge(one(p(PLAIN)), one(p(later))).kind == "conflict"


def test_other_games_need_exact_scores(p):
    k = "Krillion #107 🦐\n{}\n\n🐟🐟🏮🦑🐟🦑🫧"
    assert merge(one(p(k.format(285))), one(p(k.format(286)))).kind == "conflict"
    assert merge(one(p(k.format(285))), one(p(k.format(285) + "\nhttps://krillion.io"))).kind == "duplicate"


def test_partial_paste_is_completed_by_a_later_one(p):
    broken = one(p("Krillion #107 🦐\n\n🐟🐟🏮🦑🐟🦑🫧"))
    m = merge(broken, one(p("Krillion #107 🦐\n310\n\n🐟🐟🏮🦑🐟🦑🫧")))
    assert m.kind == "enrich" and m.result.metrics == {"score": 310} and "score" in m.added
