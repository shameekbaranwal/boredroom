"""One case per share-text shape. Each case: (paste, expected subset of the result)."""
import pytest

from ..conftest import one

CASES = {
    "maptap": [(
        "www.maptap.gg October 12\n100🎯 94🏅 87🎓 94🏆 95🏅\nFinal score: 935",
        dict(puzzle="2026-10-12", metrics={"score": 935}, status="late"),
    )],
    "krillion": [(
        "Krillion #98 🦐\n310\n\n🐟🐟🐟🐟🦑🌟🐟",
        dict(puzzle=98, metrics={"score": 310}, highlights=["krill"], extras={"krills": 1}),
    ), (
        "Krillion #89 🦐\n440\n\n🏮🦑🦑🐟🦑🦑🏮\nhttps://krillion.io",
        dict(puzzle=89, metrics={"score": 440}, highlights=[], comment=""),
    )],
    "connections": [(
        "Connections\nPuzzle #1219\n🟦🟦🟦🟦\n🟨🟨🟨🟨\n🟩🟩🟩🟩\n🟪🟪🟪🟪",
        dict(puzzle=1219, outcome="solved", metrics={"mistakes": 0}, highlights=["flawless"]),
    ), (
        "Connections\nPuzzle #1220\n🟩🟦🟩🟩\n🟩🟦🟩🟩\n🟩🟩🟩🟩\n🟨🟨🟨🟨\n🟦🟦🟦🟪\n🟦🟦🟦🟪",
        dict(outcome="failed", metrics={"mistakes": 4}),
    ), (
        "Connections\nPuzzle #1220\n🟩🟦🟩🟩\n🟩🟩🟩🟩\n🟨🟨🟨🟨\n🟦🟦🟦🟦\n🟪🟪🟪🟪",
        dict(outcome="solved", metrics={"mistakes": 1}, highlights=[]),
    )],
    "wiki": [(
        "Seawater ➡️ Babe Ruth ⏰ 03:23 🦶6 (Seawater ➡️ Water ➡️ Ice skating ➡️ Rinkball ➡️ Ball sport ➡️ Baseball ➡️ Babe Ruth) 🔗 https://www.thewikigamedaily.com",
        dict(puzzle="seawater → babe ruth", metrics={"steps": 6, "time": 203}, comment=""),
    ), (
        "Seawater ➡️ Babe Ruth ⏰ 02:09 🦶5 🔗 https://www.thewikigamedaily.com",
        dict(metrics={"steps": 5, "time": 129}),
    )],
    "anno": [(
        "ANNO №284\n90🎯  63👍  19💀  10💀  51👍\nTotal: 233/500\n\nhttps://anno-game.netlify.app\n\nGone",
        dict(puzzle=284, metrics={"score": 233}, comment="Gone", confidence="exact"),
    ), (
        "97🎯  94🎯  26🤔  0💀  12💀\n229/500\n\nhttps://anno-game.netlify.app",
        dict(metrics={"score": 229}, confidence="inferred"),
    )],
    "pindrop": [(
        "📍 PlayPinDrop Day #239\n🟢 🟢 🎯 🎯 🎯\n976 / 1000\nNew personal best!\n🏆 Beat the 910 challenge! Rounds: 2-0.\nhttps://playpindrop.app?r=wt0emiho",
        dict(puzzle=239, metrics={"score": 976}, highlights=["personal best", "challenge won"], comment=""),
    ), (
        "📍 PlayPinDrop Day #223\n🟢 🟢 🟢 🟠 🟡\n788 / 1000\n🔥 20 day streak\nhttps://playpindrop.app?r=4w25qerp",
        dict(metrics={"score": 788}, extras={"game_streak": 20}),
    )],
    "fermi": [(
        "Fermi · No. 78\n01  32.3×\n02  195,288,089×\n03  5.56×\n─────────\n56.4× score · top 90%\n<https://fermi.gg/s/daily>",
        dict(puzzle=78, metrics={"score": 56.4}, extras={"percentile": 90}, comment=""),
    )],
    "metazooa": [(
        "🐋 Animal #1169 🐉\nI figured it out in 5 guesses!\n🟧🟨🟩🟩🟩\n🔥 13 | Avg. Guesses: 7.6\n    \nhttps://metazooa.com\n#metazooa",
        dict(puzzle=1169, metrics={"guesses": 5}, extras={"game_streak": 13}, comment=""),
    ), (
        "🦄 Animal #1171 🐎\nI was stumped by today's game!\n🟥🟧🟨🟨🟨🟩🟩🟩🟩🟨🟩🟩🟥🟨🟨🟩🟩🟩🟩🟩\n🔥 0 | Avg. Guesses: 8.6\nhttps://metazooa.com\n#metazooa",
        dict(outcome="failed", metrics={}),
    )],
    "strands": [(
        "Strands #953\n“In a manner of speaking”\n💡🔵🔵🔵\n🔵🟡🔵",
        dict(puzzle=953, metrics={"hints": 1, "spangram": 5}),
    ), (
        "Strands #955\n“Folk & fairy tale twosomes”\n🟡🔵🔵🔵\n🔵🔵🔵",
        dict(metrics={"hints": 0, "spangram": 1}, highlights=["no hints", "spangram first"]),
    )],
    "globle": [(
        "🌎 Oct 12, 2026 🌍\n🔥 8 | Avg. Guesses: 6.9\n🟧🟥🟧🟥🟥🟥🟩 = 7\n\nhttps://globle-game.com\n#globle",
        dict(puzzle="2026-10-12", metrics={"guesses": 7}, extras={"game_streak": 8}, comment=""),
    ), (
        "Globle Stats 🌎 Oct 25, 2026 🌍\n🔥 1 | Avg. Guesses: 12.25\n🟧🟧🟥🟧🟧🟥🟧🟧\n🟥🟥🟥🟥🟥🟥🟩 = 15\n\nhttps://globle-game.com\n#globle",
        dict(puzzle="2026-10-25", metrics={"guesses": 15}),
    )],
    "cryptic": [(
        "Minute Cryptic - 12 October, 2026\n\"Odds of guys accepting defeat in a photo finish?\" (6)\n⚪️🟣🟣🟣🟣🟣🟣🟣🟣\n🏆 1 hints – 1 under the community par (38,650 solvers so far). Time: 1m 7s.\nhttps://www.minutecryptic.com/?utm_source=share",
        dict(puzzle="2026-10-12", metrics={"hints": 1, "time": 67}, highlights=["under par"], comment=""),
    ), (
        "Minute Cryptic - 14 October, 2026\n\"Mr. Ying after getting PhD for H2O removal\" (6)\n⚪️🟣🟣🟣🟣🟣🟣🟣🟣\n🤝 1 hints – matched the community par (49,828 solvers so far).\nhttps://www.minutecryptic.com/?utm_source=share",
        dict(metrics={"hints": 1}, highlights=["matched par"]),
    )],
    "perceptle": [(
        "Perceptle #100 - B (76)\n🔢 89  🎯 99  📐 97  🥁 97  ✂️ 0\nhttps://perceptle.com",
        dict(puzzle=100, metrics={"score": 76}),
    ), (
        "Perceptle #101 🃏 - C (63)\n🔢 27  🎯 85  📐 99  🥁 6  ✂️ 96\nhttps://perceptle.com",
        dict(metrics={"score": 63}),
    )],
    "travle": [(
        "#travle #1405 +3\n🟧🟧✅🟧🟩🟩✅\nhttps://travle.earth",
        dict(puzzle=1405, metrics={"over": 3}, highlights=[]),
    ), (
        "#travle #1406 +0 (Perfect)\n✅✅✅\nhttps://travle.earth",
        dict(metrics={"over": 0}, highlights=["perfect"]),
    )],
    "sdd": [(
        "System Design Daily #1001\n\n🟥🟩🟥🟩🟩\n\nhttps://systemdesigndaily.com/quiz",
        dict(puzzle=1001, metrics={"correct": 3}, comment=""),
    )],
    "red": [(
        "Daily Red #2: Beat Red\n⬛⬛🟩⬛⬛⬛  1/6 left · 19 turns\nStreak 1 · #DailyRed\ndaily-red.com",
        dict(puzzle=2, outcome="solved", metrics={"left": 1, "turns": 19}),
    ), (
        "Daily Red #4: Red won\n🟥⬛🟥🟥🟥🟥  5/6 KO'd · 21 turns\n#DailyRed\ndaily-red.com",
        dict(outcome="failed", metrics={"knocked": 5, "turns": 21}),
    )],
    "orbs": [(
        "DailyOrbs October 11 2026\nhttps://DailyOrbs.com/2026-10-11?utm_source=share\n🟠🟢💚🔵🟣💜💜🟢🟢🏆",
        dict(puzzle="2026-10-11", outcome="played", metrics={"orbs": 6, "lives_lost": 3}),
    )],
    "noillirk": [(
        "Noillirk daily #30 - 6,763m\nTHE THUNDERHEAD\n\n🟨⬛⬜🟥🟥🟨🟨\n\nhttps://playdaily.org/noillirk",
        dict(puzzle=30, metrics={"distance": 6763}, comment=""),
    ), (
        "Noillirk daily #31 - 1.2km\nTHE VALLEY\n\n🟩🟩⬜🟥🟦⬜🟦",
        dict(metrics={"distance": 1200}),
    )],
    "pyragrams": [(
        "Pyragrams: Sat, 10/24/2026 ✅\n🎯 2 🔀 11 🕓 2:23\n       ▪️\n   🟪      🟪\n 🟪  🟪  🟪  🟪\n🟪🟪🟪🟪🟩🟪🟩🟪\n<https://www.pyralinks.com/puzzle/pyragrams>",
        dict(puzzle="2026-10-24", metrics={"moves": 11, "time": 143}, comment=""),
    )],
    "pyraphemes": [(
        "Pyraphemes: Sat, 10/24/2026 ✅\n🎯 3 🔀 24 🕓 6:13\n       ▪️\n   🟩      🟩\n<https://www.pyralinks.com/puzzle/pyraphemes>",
        dict(puzzle="2026-10-24", metrics={"moves": 24, "time": 373}, comment=""),
    )],
    "pyrithmetic": [(
        "Pyrithmetic: Sun, 10/25/2026 ✅\n🎯 4 🔀 54 🕓 13:38\n\n   🟪\n 🟩  🟩\n🟩🟩🟩🟩\n<https://www.pyralinks.com/puzzle/pyrithmetic>",
        dict(puzzle="2026-10-25", metrics={"moves": 54, "time": 818}),
    )],
    "wordle": [(
        "Wordle 1,959 3/6\n\n⬛⬛🟩⬛🟩\n⬛🟩🟩⬛🟩\n🟩🟩🟩🟩🟩",
        dict(puzzle=1959, metrics={"guesses": 3}),
    ), (
        "Wordle 1,959 X/6\n\n⬛⬛🟩⬛🟩",
        dict(outcome="failed", metrics={}),
    )],
    "mini": [(
        "I solved the 10/13/2026 New York Times Mini Crossword in 1:32!\n\nhttps://nytimes.onelink.me/IM32/7owuagxr",
        dict(puzzle="2026-10-13", metrics={"time": 92}),
    )],
    "layers": [(
        "🏆 Layers #347\n🗓 Oct 25, 2026\n\n🟧🟧🟧🟧 ⬛⬛🟩🟧🟧\n🟪🟪🟪🟪 🟧⬛🟩⬛🟩\n🟩🟩🟩🟩 ⬛🟩🟩⬛🟩\n🟦🟦🟦🟦 ⬛🟩🟩⬛🟩\n         🟩🟩🟩🟩🟩\n         5/6 ✅\n\n📝✅ 🔍✅ 🔀 2 🔥 1\n\nPlay today's layers:\nhiddenlayerlabs.com/layers",
        dict(puzzle=347, metrics={"guesses": 5}, comment=""),
    )],
    "historydle": [(
        "Historydle #1031 - Classic\n\n⬛⬛⬛⬛⬛\n⬛🟩⬛⬛⬛\n🟩🟩🟩🟩🟩\n\nhttps://historydle.com",
        dict(puzzle=1031, metrics={"guesses": 3}),
    )],
    "petguessr": [(
        "PetGuessr #106 — 5/10\n🐱🐶🐱🐶❌\n❌❌🐶❌❌\nhttps://petguessr.com",
        dict(puzzle=106, metrics={"correct": 5}, comment=""),
    )],
    "pips": [(
        "Pips #421 Medium 🟡\n0:34 🍪",
        dict(puzzle=421, metrics={"level": 2, "time": 34}),
    )],
}


def _cases():
    for game, cases in CASES.items():
        for i, (text, want) in enumerate(cases):
            yield pytest.param(game, text, want, id=f"{game}-{i}")


@pytest.mark.parametrize("game,text,want", list(_cases()))
def test_game(p, game, text, want):
    r = one(p(text))
    got = r.to_dict()
    assert got["game"] == game
    for k, v in want.items():
        assert got[k] == v, (k, got)
    if "confidence" not in want:
        assert got["confidence"] == "exact", got["warnings"]


def test_every_game_has_a_case():
    from boredroom.parser import REGISTRY
    missing = {g for g, c in REGISTRY.items() if not c.ignore} - set(CASES)
    assert not missing, missing


def test_connections_bonus_is_ignored(p):
    got = p("Connections 3x3\nBonus October 14, 2026\n\n🟪🟪🟪\n🟨🟨🟨\n🟦🟦🟦")
    assert not got.results and got.ignored == ["connections-bonus"]
