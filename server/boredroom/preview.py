"""Link previews: the card a chat app shows when someone pastes a boredroom link.

An invite's card is drawn here, per invite, so the group sees who saved them a seat and
where; every other link shares the static card in the web build (web/public/og.png).
"""
from __future__ import annotations

import io
import random
import re
import zlib
from html import escape
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import Invite

FONTS = Path(__file__).with_name("fonts")
W, H = 1200, 630
GREEN, INK, WHITE, YELLOW = "#217346", "#1d1f1e", "#ffffff", "#ffd84d"
PALE, CHIP = "#cfe8d8", "#195c37"


def _font(size: int, weight: str = "Black") -> ImageFont.FreeTypeFont:
    if weight == "mono":
        return ImageFont.truetype(str(FONTS / "IBMPlexMono-Regular.ttf"), size)
    f = ImageFont.truetype(str(FONTS / "LibreFranklin.ttf"), size)
    f.set_variation_by_name(weight)
    return f


def _wordmark(d: ImageDraw.ImageDraw, x: int, y: int, size: int) -> None:
    """boredr[o][o]m: the two o's sit in cells, white then yellow, as in the app."""
    f = _font(size)
    for part, cell, ink in (("boredr", None, WHITE), ("o", WHITE, GREEN), ("o", YELLOW, INK), ("m", None, WHITE)):
        w = d.textlength(part, font=f)
        if cell:
            top = y + size * .30
            d.rectangle((x + 2, top, x + w + size * .1, y + size * 1.02), fill=cell)
            x += size * .05
        d.text((x, y), part, font=f, fill=ink)
        x += w + (size * .1 if cell else 0)


def _wrap(d: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and d.textlength(trial, font=f) > width:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line] if line else lines


def _fit(d: ImageDraw.ImageDraw, text: str, width: int, sizes: tuple[int, ...], max_lines: int):
    """The biggest size at which `text` fits in `max_lines` lines."""
    for size in sizes:
        f = _font(size)
        lines = _wrap(d, text, f, width)
        if len(lines) <= max_lines:
            return f, lines
    return f, lines[:max_lines]


def _table(d: ImageDraw.ImageDraw, cx: int, cy: int, board: str, names: list[str]) -> None:
    """The board around a table, seen from above, its name on the table; the yellow
    outlined seat at the head is the one saved."""
    tw, th = 300, 150
    d.rounded_rectangle((cx - tw / 2, cy - th / 2, cx + tw / 2, cy + th / 2), radius=th / 2, fill=WHITE)
    tf, _ = _fit(d, board, tw - 70, (46, 40, 34, 28, 24), 1)
    d.text((cx, cy - 6), board if d.textlength(board, font=tf) <= tw - 70 else board[:14] + "…", font=tf, fill=GREEN, anchor="mm")
    d.text((cx, cy + 30), "the board", font=_font(17, "mono"), fill="#6b6b6b", anchor="mm")
    f = _font(20, "Bold")
    rows = [(-1, names[0:3]), (1, names[3:6])]
    for sy, row in rows:
        for i, name in enumerate(row):
            x, y = cx + (i - 1) * tw * .34, cy + sy * (th / 2 + 34)
            name = name if len(name) <= 8 else name[:7] + "…"
            w = d.textlength(name, font=f) + 24
            d.rectangle((x - w / 2, y - 18, x + w / 2, y + 18), fill=CHIP)
            d.text((x, y), name, font=f, fill=WHITE, anchor="mm")
    # the empty seat, at the head of the table
    x = cx - tw / 2 - 58
    d.rectangle((x - 44, cy - 20, x + 44, cy + 20), outline=YELLOW, width=3)
    d.text((x, cy), "you?", font=f, fill=YELLOW, anchor="mm")


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _lines(d: ImageDraw.ImageDraw, x: int, y: int, f: ImageFont.FreeTypeFont, lines: list[str], fill: str) -> int:
    for ln in lines:
        d.text((x, y), ln, font=f, fill=fill)
        y += int(f.size * 1.1)
    return y


@lru_cache(maxsize=256)
def invite_card(headline: str, line: str, board: str, members: tuple[str, ...], small: str, art: str = "table") -> bytes:
    img = Image.new("RGB", (W, H), GREEN)
    d = ImageDraw.Draw(img)
    _wordmark(d, 72, 52, 64)
    room = 760 if art in ART else 600  # the table reaches further left than a game's picture
    f, lines = _fit(d, headline, room, (92, 84, 76, 68), 1)
    y = _lines(d, 72, 168, f, lines, YELLOW) + 14
    f2, lines2 = _fit(d, line, 600, (44, 40, 36, 32), 3)
    _lines(d, 72, y, f2, lines2, WHITE)
    d.text((72, H - 82), small, font=_font(26, "mono"), fill=PALE)
    if art in ART:
        ART[art](d)
    else:
        _table(d, 960, 330, board, list(members))
    return _png(img)


# the cards a plain boredroom link shows, one picked at random per fetch:
# name -> (og:title, og:description, headline lines, subline)
CARDS: dict[str, tuple[str, str, list[str], str]] = {
    "wordle": ("boredroom · every 6/6, on the record",
               "paste your wordle like always. boredroom files it, ranks it, and never lets anyone forget.",
               ["every 6/6,", "on the record."], "your group's daily puzzles, scored."),
    "connections": ("boredroom · purple first, allegedly",
                    "paste your connections grid. boredroom keeps the minutes, the scores, and the receipts.",
                    ["purple first.", "allegedly."], "now there are receipts."),
    "mini": ("boredroom · 0:52, take your time",
             "the mini, timed and ranked for your whole group. paste it like always; boredroom does the rest.",
             ["0:52.", "take your time."], "the mini, timed and ranked against your friends."),
    "cryptic": ("boredroom · solved in one, no hints",
                "minute cryptic, wordle, connections and more. paste them; boredroom keeps score for the group.",
                ["solved in one.", "no hints."], "the board has a few questions."),
}


def _wordle(d: ImageDraw.ImageDraw) -> None:
    rows = ["bybgb", "ygbgb", "ggbgb", "gggyb", "ggggb", "ggggg"]
    colors = {"g": "#6aaa64", "y": "#c9b458", "b": "#3a3a3c"}
    s, gap, x0, y0 = 42, 7, 905, 150
    for r, row in enumerate(rows):
        for c, k in enumerate(row):
            x, y = x0 + c * (s + gap), y0 + r * (s + gap)
            d.rectangle((x, y, x + s, y + s), fill=colors[k])


def _connections(d: ImageDraw.ImageDraw) -> None:
    # a mistake first, then purple, then the rest: the grid people post
    rows = ["pyyp", "pppp", "bbbb", "gggg", "yyyy"]
    colors = {"y": "#f9df6d", "g": "#a0c35a", "b": "#b0c4ef", "p": "#ba81c5"}
    s, gap, x0, y0 = 52, 8, 890, 150
    for r, row in enumerate(rows):
        for c, k in enumerate(row):
            x, y = x0 + c * (s + gap), y0 + r * (s + gap)
            d.rounded_rectangle((x, y, x + s, y + s), radius=8, fill=colors[k])


def _mini(d: ImageDraw.ImageDraw) -> None:
    black = {(0, 0), (4, 4)}
    s, x0, y0 = 54, 880, 140
    for r in range(5):
        for c in range(5):
            x, y = x0 + c * s, y0 + r * s
            d.rectangle((x, y, x + s, y + s), fill=INK if (r, c) in black else WHITE, outline=INK, width=2)
    f = _font(30, "Bold")
    for r, word, start in ((0, "memo", 1), (1, "chair", 0)):
        for c, ch in enumerate(word):
            d.text((x0 + (start + c) * s + s / 2, y0 + r * s + s / 2 + 2), ch, font=f, fill=INK, anchor="mm")
    d.rounded_rectangle((x0 + 60, y0 + 5 * s + 22, x0 + 5 * s - 60, y0 + 5 * s + 78), radius=28, fill=YELLOW)
    d.text((x0 + 5 * s / 2, y0 + 5 * s + 50), "0:52", font=_font(34), fill=INK, anchor="mm")


def _cryptic(d: ImageDraw.ImageDraw) -> None:
    x0, y0, w = 850, 150, 290
    d.rounded_rectangle((x0, y0, x0 + w, y0 + 250), radius=14, fill=WHITE)
    f = _font(25, "SemiBold")
    for i, ln in enumerate(["drilled, and not", "interested (5)"]):
        d.text((x0 + 22, y0 + 26 + i * 34), ln, font=f, fill=INK)
    s = 46
    for c, ch in enumerate("bored"):
        x = x0 + 22 + c * (s + 6)
        d.rectangle((x, y0 + 120, x + s, y0 + 120 + s), outline=GREEN, width=3)
        d.text((x + s / 2, y0 + 120 + s / 2), ch, font=_font(28), fill=GREEN, anchor="mm")
    d.text((x0 + 22, y0 + 196), "hints used: 0", font=_font(20, "mono"), fill="#6b6b6b")


GAME_OF = {"wordle": "wordle", "connections": "connections", "mini": "mini", "cryptic": "cryptic"}  # card art -> game id
ART = {"wordle": _wordle, "connections": _connections, "mini": _mini, "cryptic": _cryptic}


@lru_cache(maxsize=8)
def generic_card(name: str = "wordle") -> bytes:
    """A plain link's preview card; web/public/og.png is the wordle one."""
    _, _, lines, sub = CARDS[name]
    img = Image.new("RGB", (W, H), GREEN)
    d = ImageDraw.Draw(img)
    _wordmark(d, 72, 60, 84)
    size = 92 if len(lines) == 2 else 80
    y = _lines(d, 72, 210, _font(size), lines, WHITE)
    d.text((72, y + 14), sub, font=_font(32, "SemiBold"), fill=PALE)
    d.text((72, H - 82), "boredroom.shmk.dev", font=_font(26, "mono"), fill=PALE)
    ART[name](d)
    return _png(img)


# -- the page's tags --------------------------------------------------------------

def _set(html: str, attr: str, key: str, value: str) -> str:
    """Rewrites the content of <meta {attr}="{key}" content="...">."""
    return re.sub(rf'(<meta {attr}="{re.escape(key)}" content=")[^"]*(")', lambda m: m[1] + escape(value, quote=False).replace('"', "&quot;") + m[2], html)


def tags(html: str, origin: str, invite: Invite | None) -> str:
    """index.html with its preview tags for this instance and, for an invite, that invite."""
    html = html.replace("https://boredroom.shmk.dev/", f"{origin}/")
    if invite is None:
        name = random.choice(list(CARDS))
        title, description, _, _ = CARDS[name]
        for attr, key, value in (("property", "og:title", title), ("property", "og:description", description),
                                 ("property", "og:image", f"{origin}/og/{name}.png")):
            html = _set(html, attr, key, value)
        return html
    t = invite_text(invite)
    for attr, key, value in (
        ("property", "og:title", t["title"]), ("property", "og:description", t["description"]),
        ("name", "description", t["description"]),
        ("property", "og:image", f"{origin}/og/invite/{invite.code}.png"),
        ("property", "og:url", f"{origin}/join/{invite.code}"),
    ):
        html = _set(html, attr, key, value)
    return html.replace("<title>boredroom</title>", f"<title>{escape(t['title'])}</title>")


def _people(invite: Invite) -> tuple[str, str, list[str]]:
    live = [m for m in invite.board.memberships if m.left_at is None]
    chair = next((m.nickname for m in live if m.role == "chair"), None)
    inviter = next((m.nickname for m in live if m.person_id == invite.created_by), None) or chair or "a friend"
    # first names read best on a small card; the inviter is already in the headline
    others = [m.nickname.split()[0] for m in sorted(live, key=lambda m: m.joined_at) if m.nickname != inviter]
    return inviter, invite.board.name, others


def invite_text(invite: Invite) -> dict[str, str]:
    """The words of an invite's preview (copy by fable: "saved seat")."""
    inviter, board, others = _people(invite)
    n, games = len(others) + 1, len(invite.board.library)
    plural = lambda k, w: f"{k} {w}{'' if k == 1 else 's'}"
    return {
        "title": f"{inviter} saved you a seat",
        "description": f"{board}: {plural(n, 'member')}, {plural(games, 'game')}, one empty seat. "
                       "it's yours if you want it. held for 24 hours.",
        "headline": "reserved for you.",
        "line": f"{inviter} saved you a seat at {board}'s table.",
        "small": f"{invite.code.replace('-', ' ')} · held for 24 hours",
    }


def invite_png(invite: Invite) -> bytes:
    inviter, board, others = _people(invite)
    t = invite_text(invite)
    # the table, or a picture of a game this board plays; the same one every time for an invite
    plays = {bg.game_id for bg in invite.board.library}
    arts = ["table"] + [a for a, game in GAME_OF.items() if game in plays]
    art = arts[zlib.crc32(invite.code.encode()) % len(arts)]
    return invite_card(t["headline"], t["line"], board, tuple(others[:6]), t["small"], art)
