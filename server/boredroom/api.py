"""JSON API, /api/v1. See docs/SERVER.md part 5.

Handlers commit; services (filing, boards) only flush.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from flask import Blueprint, Response, current_app, g, jsonify, request
from sqlalchemy import func, select

from . import admin, boards, claims, filing, invites, memos, names, news, people, push, reads, throttle
from . import auth
from .auth import auth_required, create_guest, valid_tz, USERNAME
from .errors import ApiError, fail
from .models import Agenda, AuthToken, Board, Feedback, Membership, Person, Result, utcnow
from .parser import REGISTRY

api = Blueprint("api", __name__, url_prefix="/api/v1")


def body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    if data is None:
        return {}
    if not isinstance(data, dict):
        fail(400, "send a json object")
    return data


def clock():
    """The time memos are read at: now, unless a test set the app's CLOCK."""
    return current_app.config.get("CLOCK", lambda: None)()


AGENDA_SORTS = {"usual", "own", "resets", "mine", "popular", "busy", "tenure", "name"}  # web/src/sort.ts


def me_json(p: Person) -> dict[str, Any]:
    live = [m for m in p.memberships if m.left_at is None]
    return {
        "username": p.username, "kind": p.kind, "tz": p.tz, "email": p.email, "agenda_sort": p.agenda_sort,
        "reset_clock": p.reset_clock, "paste_check": p.paste_check,
        "boards": [{"slug": m.board.slug, "name": m.board.name, "nickname": m.nickname, "role": m.role}
                   for m in sorted(live, key=lambda m: m.board.name)],
        "news": news.card(p),  # the agenda's "what's new" card
    }


# -- what's new, and notes to the developer ----------------------------------------

@api.get("/news")
@auth_required
def news_list():
    """Every release, newest first, the newest one you've read, and the answers to your notes."""
    return jsonify({"releases": [news.release_json(r) for r in news.RELEASES], "seen": g.person.news_seen,
                    "replies": [news.reply_json(f) for f in news.replies(g.db, g.person)]})


@api.post("/news/seen")
@auth_required
def news_seen():
    """{id}: you've read up to this release; its card leaves the agenda."""
    news.seen(g.person, str(body().get("id", "")))
    g.db.commit()
    return jsonify(me_json(g.person))


FEEDBACK_KINDS = ("bug", "idea")


@api.post("/feedback")
@auth_required
def feedback_new():
    """{kind: bug|idea, text, board?}: a note to the developer."""
    b = body()
    kind, text = b.get("kind"), b.get("text")
    if kind not in FEEDBACK_KINDS:
        fail(400, "a note is a bug or an idea")
    if not isinstance(text, str) or not text.strip():
        fail(400, "write something first")
    if len(text) > 2000:
        fail(400, "keep it under 2000 characters")
    throttle.limit(g.db, f"feedback:{g.person.id}", 10, 3600, "that's a lot of notes for one hour. the developer is reading.")
    slug = b.get("board")
    board = slug if isinstance(slug, str) and any(m.board.slug == slug for m in g.person.memberships) else None
    g.db.add(Feedback(person_id=g.person.id, kind=kind, text=text.strip(), board=board, release=news.LATEST.id,
                      device=request.headers.get("User-Agent", "")[:200]))
    g.db.commit()
    return jsonify(_my_notes()), 201


@api.get("/feedback")
@auth_required
def feedback_mine():
    """The notes you've sent, newest first."""
    return jsonify(_my_notes())


def _my_notes() -> list[dict[str, Any]]:
    rows = g.db.scalars(select(Feedback).where(Feedback.person_id == g.person.id).order_by(Feedback.created_at.desc()).limit(50))
    return [{"id": f.id, "kind": f.kind, "text": f.text, "board": f.board, "sent_at": f.created_at.isoformat()} for f in rows]


# -- people ----------------------------------------------------------------------

@api.post("/guests")
def new_guest():
    throttle.limit(g.db, f"guest:{throttle.caller()}", 10, 3600, "that's a lot of new seats from here. try again in an hour.")
    b = body()
    tz = auth.browser_tz(b.get("tz"), current_app.config["BOREDROOM"].default_tz)
    person, token = create_guest(g.db, b.get("username"), tz, request.headers.get("User-Agent", "")[:200])
    g.db.commit()
    return jsonify({"token": token, "me": me_json(person)}), 201


@api.get("/usernames/<name>")
def username_check(name):
    """Is this username free? For the live check as someone types. One indexed lookup.
    Signed-in callers get "yours" for their own."""
    throttle.limit(g.db, f"uname:{throttle.caller()}", 300, 600, "slow down: too many username checks")
    name = name.strip().lower()[:40]
    if not USERNAME.match(name):
        return jsonify({"username": name, "available": False, "reason": "2–30 characters: letters, digits, . _ -"})
    owner = g.db.scalar(select(Person.id).where(Person.username == name))
    token = auth.bearer()
    row = token and auth.token_row(g.db, token)
    me = row.person if row else None
    if owner is not None and me is not None and owner == me.id:
        return jsonify({"username": name, "available": True, "reason": "that's you"})
    return jsonify({"username": name, "available": owner is None, "reason": None if owner is None else "taken"})


@api.get("/config")
def client_config():
    """What a client needs before signing in. The google client id is public by design."""
    cfg = current_app.config["BOREDROOM"]
    return jsonify({"google_client_id": cfg.google_client_id, "environment": cfg.environment,
                    "vapid_public_key": cfg.vapid_public_key if cfg.push else None,
                    # the web build being served, and the latest release: an open app reloads for them
                    "web_build": current_app.config.get("WEB_BUILD"),
                    "release": {"id": news.LATEST.id, "title": news.LATEST.title}})


@api.post("/auth/google")
def google_sign_in():
    """{credential: <google id token>, tz?}. Signed in as a guest, the seat becomes the
    account (history kept), or folds into it if the account already exists; otherwise it
    signs in to, or creates, the google account."""
    client_id = current_app.config["BOREDROOM"].google_client_id
    if not client_id:
        fail(503, "google sign-in isn't set up on this server")
    b = body()
    credential = b.get("credential")
    if not isinstance(credential, str) or not credential:
        fail(400, "send the google credential")
    if len(credential) > 4096:
        fail(400, "that isn't a google credential")
    throttle.limit(g.db, f"google:{throttle.caller()}", 30, 600, "too many sign-in attempts. try again in a few minutes.")
    verify = current_app.config.get("GOOGLE_VERIFY", auth.verify_google)  # swapped in tests
    who = verify(credential, client_id)
    row = auth.token_row(g.db, auth.bearer())
    tz = auth.browser_tz(b.get("tz"), current_app.config["BOREDROOM"].default_tz)
    person, token, created, merged = auth.sign_in_google(
        g.db, who, tz, row.person if row else None, request.headers.get("User-Agent", "")[:200])
    g.db.commit()
    return jsonify({"token": token, "created": created, "merged": merged, "me": me_json(person)}), 201 if created else 200


@api.post("/auth/signout")
@auth_required
def sign_out():
    g.db.delete(g.token)
    g.db.commit()
    return jsonify({"signed_out": True})


@api.get("/me")
@auth_required
def me():
    return jsonify(me_json(g.person))


@api.patch("/me")
@auth_required
def update_me():
    b = body()
    if "tz" in b:
        if not isinstance(b["tz"], str) or len(b["tz"]) > 64:
            fail(400, "timezones are names like asia/kolkata")
        tz = auth.TZ_ALIASES.get(b["tz"], b["tz"])
        if not valid_tz(tz):
            fail(400, f"unknown timezone {b['tz']}")
        g.person.tz = tz
    if "username" in b:
        name = str(b["username"]).strip().lower()
        if not USERNAME.match(name):
            fail(400, "usernames are 2–30 characters: letters, digits, . _ -")
        if name != g.person.username and g.db.scalar(select(Person.id).where(Person.username == name)):
            fail(409, "that username is taken")
        g.person.username = name
    if "reset_clock" in b:  # resets as a clock time ("till 9:30 am") or time left, on every device
        if not isinstance(b["reset_clock"], bool):
            fail(400, "reset_clock is true or false")
        g.person.reset_clock = b["reset_clock"]
    if "paste_check" in b:  # a paste shows what the clerk read and waits for save, or files at once
        if not isinstance(b["paste_check"], bool):
            fail(400, "paste_check is true or false")
        g.person.paste_check = b["paste_check"]
    if "agenda_sort" in b:  # how your agenda is ordered, on every device
        v = b["agenda_sort"]
        by, _, order = v.partition(":") if isinstance(v, str) else ("", "", "")
        if v is not None and (by not in AGENDA_SORTS or order not in ("first", "last")):
            fail(400, f"agenda_sort is one of {', '.join(sorted(AGENDA_SORTS))}, then :first or :last")
        g.person.agenda_sort = None if v is None or v == "usual:first" else v
    g.db.commit()
    return jsonify(me_json(g.person))


# -- reminders: this person's devices -----------------------------------------------

def _sender() -> push.Sender:
    return current_app.config.get("PUSH_SENDER", push.webpush_sender)  # swapped in tests


@api.get("/me/push")
@auth_required
def push_devices():
    return jsonify({"available": current_app.config["BOREDROOM"].push, "devices": push.devices_json(g.db, g.person)})


@api.put("/me/push")
@auth_required
def push_subscribe():
    """{endpoint, keys: {p256dh, auth}}: this device takes reminders. Idempotent."""
    if not current_app.config["BOREDROOM"].push:
        fail(503, "reminders aren't set up on this server")
    push.subscribe(g.db, g.person, body(), request.headers.get("User-Agent", "")[:300])
    g.db.commit()
    return jsonify({"devices": push.devices_json(g.db, g.person)})


@api.post("/me/push/renew")
def push_renew():
    """{old, sub}: the service worker, after the browser replaced a subscription. It has no
    token; knowing the old endpoint (a secret the push service handed this device) is enough."""
    throttle.limit(g.db, f"renew:{throttle.caller()}", 20, 3600, "too many renewals from here")
    b = body()
    old = g.db.scalar(select(push.PushSubscription).where(push.PushSubscription.endpoint == str(b.get("old", ""))))
    if old is None:
        fail(404, "no such device")
    person = g.db.get(Person, old.person_id)
    sub = b.get("sub") if isinstance(b.get("sub"), dict) else {}
    if sub.get("endpoint") != old.endpoint:
        g.db.delete(old)
        g.db.flush()
    push.subscribe(g.db, person, sub, request.headers.get("User-Agent", "")[:300])
    g.db.commit()
    return jsonify({"renewed": True})


@api.delete("/me/push/<int:sid>")
@auth_required
def push_unsubscribe(sid):
    sub = g.db.get(push.PushSubscription, sid)
    if sub is None or sub.person_id != g.person.id:
        fail(404, "no such device")
    g.db.delete(sub)
    g.db.commit()
    return jsonify({"devices": push.devices_json(g.db, g.person)})


@api.post("/me/push/test")
@auth_required
def push_test():
    """A test memo to every device you have."""
    cfg = current_app.config["BOREDROOM"]
    if not cfg.push:
        fail(503, "reminders aren't set up on this server")
    throttle.limit(g.db, f"pushtest:{g.person.id}", 5, 3600, "that's enough tests for an hour. the board can reach you.")
    sent = push.deliver(g.db, g.person.id, push.Push("test memo: the board can reach you.",
                        "this is what a reminder looks like. turn them off under you → everywhere.", "/desk", "test"),
                        cfg, _sender())
    return jsonify({"sent": sent, "devices": push.devices_json(g.db, g.person)})


@api.get("/me/leaving")
@auth_required
def leaving():
    """What deleting your account would do, board by board."""
    out = []
    for m in g.db.scalars(select(Membership).where(Membership.person_id == g.person.id, Membership.left_at.is_(None))):
        out.append(boards.leaving_json(g.db, m.board, g.person))
    return jsonify(out)


@api.delete("/me")
@auth_required
def close_account():
    """{username}: deletes your account and everything that's yours. Typing the username
    back is the confirmation. Seats claimed from a chat history go back unclaimed."""
    if str(body().get("username", "")).strip().lower() != g.person.username:
        fail(400, "type your username to confirm")
    if g.person.kind == "placeholder":
        fail(403, "placeholders can't close accounts")
    f = admin.close_account(g.db, g.person)
    g.db.commit()
    return jsonify({"deleted": True, "boards_closed": f.boards_deleted})


# -- the library -----------------------------------------------------------------

@api.get("/games")
def games():
    return jsonify([{"id": c.id, "name": c.name, "key": c.key, "ranked": c.ranked(), "weekly": c.weekly(),
                     "links": list(c.links), "play": c.play_url(), "ranker": list(c.ranker),
                     "metrics": [{"name": m.name, "kind": m.kind, "better": m.better, "max": m.max,
                                  "unit": m.unit} for m in c.metrics]}
                    for c in sorted(REGISTRY.values(), key=lambda c: c.name) if not c.ignore])


# -- boards ----------------------------------------------------------------------

@api.post("/boards")
@auth_required
def new_board():
    throttle.limit(g.db, f"board:{g.person.id}", 10, 86400, "that's enough new boards for one day")
    board = boards.create_board(g.db, g.person, body().get("name", ""))
    g.db.commit()
    m = g.db.get(Membership, (board.id, g.person.id))
    return jsonify(boards.board_json(g.db, board, m)), 201


@api.get("/invites/<code>")
def invite(code):
    """What an invitation shows before you join. No sign-in needed: the code is the key."""
    inv = invites.lookup(g.db, code)
    board = inv.board
    live = [m for m in board.memberships if m.left_at is None]
    chair = next((m.nickname for m in live if m.role == "chair"), None)
    # who handed it out, by their name on this board; invites made by the system read as the chair's
    inviter = next((m.nickname for m in live if m.person_id == inv.created_by), None) or chair
    return jsonify({"code": inv.code, "name": board.name, "slug": board.slug, "chair": chair, "inviter": inviter,
                    "members": len(live),
                    # imported seats, so a newcomer can say "that's me" as they join
                    "seats": [{"username": p.username, "nickname": m.nickname,
                               "results": g.db.scalar(select(func.count()).select_from(Result).where(Result.person_id == p.id))}
                              for p, m in claims.placeholders(g.db, board)],
                    "library": [REGISTRY[bg.game_id].name for bg in sorted(board.library, key=lambda b: b.game_id)]})


@api.post("/boards/join")
@auth_required
def join_board():
    board = boards.join(g.db, g.person, str(body().get("code", "")), body().get("claim") or None)
    g.db.commit()
    m = g.db.get(Membership, (board.id, g.person.id))
    return jsonify(boards.board_json(g.db, board, m))


@api.post("/boards/<slug>/invite")
@auth_required
def renew_invite(slug):
    """A fresh invite for you; your old one stops working."""
    b, m = boards.get_board(g.db, slug, g.person)
    if g.person.kind == "placeholder":
        fail(403, "placeholders don't invite")
    invites.renew(g.db, b, g.person)
    g.db.commit()
    return jsonify(boards.board_json(g.db, b, m))


@api.patch("/boards/<slug>")
@auth_required
def board_settings(slug):
    """The chair's settings: {name}. The slug stays, so links keep working."""
    b, m = boards.get_board(g.db, slug, g.person)
    if m.role != "chair":
        fail(403, "only the chair can change the board")
    b.name = names.clean(body().get("name", b.name), 60, "a board's name")
    g.db.commit()
    return jsonify(boards.board_json(g.db, b, m))


@api.delete("/boards/<slug>/invites")
@auth_required
def retire_invites(slug):
    """The chair stops every invite to the board that's out there; members get new ones."""
    b, m = boards.get_board(g.db, slug, g.person)
    if m.role != "chair":
        fail(403, "only the chair can retire everyone's invites")
    retired = invites.retire_all(g.db, b)
    g.db.commit()
    return jsonify({"retired": retired, "board": boards.board_json(g.db, b, m)})


@api.get("/boards/<slug>")
@auth_required
def board(slug):
    b, m = boards.get_board(g.db, slug, g.person)
    return jsonify(boards.board_json(g.db, b, m))


@api.patch("/boards/<slug>/me")
@auth_required
def board_me(slug):
    """{nickname?, digest?}: your seat here."""
    b, m = boards.get_board(g.db, slug, g.person)
    data = body()
    if "nickname" in data or "digest" not in data:
        nick = names.clean(data.get("nickname", ""), 40, "a nickname")
        if names.taken(g.db, b.id, nick, but=g.person.id):
            fail(409, f"someone on {b.name} already goes by {nick}")
        m.nickname = nick
    if "digest" in data:
        if not isinstance(data["digest"], bool):
            fail(400, "digest is true or false")
        m.digest = data["digest"]
    g.db.commit()
    return jsonify(boards.board_json(g.db, b, m))


@api.get("/boards/<slug>/today")
@auth_required
def board_today(slug):
    board, _ = boards.get_board(g.db, slug, g.person)
    memos.refresh(g.db, board, g.person, clock())
    out = reads.today(g.db, board, g.person) | {"memos": memos.agenda(g.db, board, g.person, clock())}
    g.db.commit()
    return jsonify(out)


@api.put("/boards/<slug>/skips/<game>")
@auth_required
def skip_game(slug, game):
    """Sits a game out until it resets, on every board. DELETE brings it back."""
    board, _ = boards.get_board(g.db, slug, g.person)
    reads.skip(g.db, g.person, game, True, clock())
    g.db.commit()
    return jsonify(reads.today(g.db, board, g.person, clock()) | {"memos": memos.agenda(g.db, board, g.person, clock())})


@api.delete("/boards/<slug>/skips/<game>")
@auth_required
def unskip_game(slug, game):
    board, _ = boards.get_board(g.db, slug, g.person)
    reads.skip(g.db, g.person, game, False, clock())
    g.db.commit()
    return jsonify(reads.today(g.db, board, g.person, clock()) | {"memos": memos.agenda(g.db, board, g.person, clock())})


@api.get("/boards/<slug>/meeting")
@auth_required
def board_meeting(slug):
    """?day=YYYY-MM-DD: the daily bored meeting, every memo reported that day (default today)."""
    board, _ = boards.get_board(g.db, slug, g.person)
    day = request.args.get("day")
    try:
        day = date.fromisoformat(day) if day else None
    except ValueError:
        fail(400, "day is YYYY-MM-DD")
    memos.refresh(g.db, board, g.person, clock())
    out = memos.meeting(g.db, board, g.person, day, clock())
    g.db.commit()
    return jsonify(out)


@api.post("/boards/<slug>/memos/<int:memo_id>/dismiss")
@auth_required
def dismiss_memo(slug, memo_id):
    """Waves a memo off your agenda, on every device. It stays in the meeting."""
    board, _ = boards.get_board(g.db, slug, g.person)
    memos.dismiss(g.db, board, g.person, memo_id, True)
    g.db.commit()
    return jsonify({"memos": memos.agenda(g.db, board, g.person, clock())})


@api.delete("/boards/<slug>/memos/<int:memo_id>/dismiss")
@auth_required
def undismiss_memo(slug, memo_id):
    board, _ = boards.get_board(g.db, slug, g.person)
    memos.dismiss(g.db, board, g.person, memo_id, False)
    g.db.commit()
    return jsonify({"memos": memos.agenda(g.db, board, g.person, clock())})


@api.get("/boards/<slug>/review")
@auth_required
def board_review(slug):
    """?period=today|week|month|all&game=&stat=&vs=: the formula bar's query (reads.review)."""
    board, _ = boards.get_board(g.db, slug, g.person)
    a = request.args
    return jsonify(reads.review(g.db, board, g.person, a.get("period", "today"), a.get("game") or None,
                                a.get("stat") or None, a.get("vs") or None))


@api.get("/boards/<slug>/members/<nickname>")
@auth_required
def board_member(slug, nickname):
    """One member's activity on the board (people.member)."""
    board, _ = boards.get_board(g.db, slug, g.person)
    return jsonify(people.member(g.db, board, g.person, nickname, clock()))


@api.get("/boards/<slug>/minutes/<game>")
@auth_required
def board_minutes(slug, game):
    """?day=YYYY-MM-DD, the puzzle's day; default is the game's current puzzle for you."""
    board, _ = boards.get_board(g.db, slug, g.person)
    boards.check_game(game)
    day = request.args.get("day")
    try:
        day = date.fromisoformat(day) if day else None
    except ValueError:
        fail(400, "day is YYYY-MM-DD")
    return jsonify(reads.minutes(g.db, board, g.person, game, day))


@api.post("/boards/<slug>/leave")
@auth_required
def leave_board(slug):
    """Gives up your seat here. A seat you claimed from the chat goes back unclaimed."""
    b, _ = boards.get_board(g.db, slug, g.person)
    closed = boards.leave(g.db, b, g.person)
    g.db.commit()
    return jsonify({"left": slug, "closed": closed})


@api.post("/boards/<slug>/claim")
@auth_required
def claim_seat(slug):
    """{username}: "that's me". Takes over an imported placeholder's history on this board."""
    board, _ = boards.get_board(g.db, slug, g.person)
    moved = claims.claim(g.db, board, g.person, str(body().get("username", "")))
    g.db.commit()
    _, m = boards.get_board(g.db, slug, g.person)
    return jsonify({"moved": moved, "board": boards.board_json(g.db, board, m)})


@api.put("/boards/<slug>/library/<game>")
@auth_required
def library_add(slug, game):
    b, m = boards.get_board(g.db, slug, g.person)
    boards.add_to_library(g.db, b, g.person, game)
    g.db.commit()
    return jsonify(boards.board_json(g.db, b, m))


@api.delete("/boards/<slug>/library/<game>")
@auth_required
def library_remove(slug, game):
    b, m = boards.get_board(g.db, slug, g.person)
    boards.remove_from_library(g.db, b, m, game)
    g.db.commit()
    g.db.refresh(b)
    return jsonify(boards.board_json(g.db, b, m))


@api.put("/boards/<slug>/agenda/<game>")
@auth_required
def agenda_add(slug, game):
    b, m = boards.get_board(g.db, slug, g.person)
    boards.set_agenda(g.db, b, g.person, game, True)
    g.db.commit()
    g.db.refresh(b)
    return jsonify(boards.board_json(g.db, b, m))


@api.delete("/boards/<slug>/agenda/<game>")
@auth_required
def agenda_remove(slug, game):
    b, m = boards.get_board(g.db, slug, g.person)
    boards.set_agenda(g.db, b, g.person, game, False)
    g.db.commit()
    return jsonify(boards.board_json(g.db, b, m))


@api.put("/boards/<slug>/order")
@auth_required
def agenda_order(slug):
    """{games: [...]}: your agenda here in your own order, for the "my order" sort."""
    b, m = boards.get_board(g.db, slug, g.person)
    games = (request.get_json(silent=True) or {}).get("games")
    if not isinstance(games, list) or not all(isinstance(x, str) for x in games) or len(games) > 200:
        fail(400, "games is a list of game ids")
    boards.set_order(g.db, b, g.person, games)
    g.db.commit()
    return jsonify(boards.board_json(g.db, b, m))


@api.put("/boards/<slug>/agenda/<game>/nudge")
@auth_required
def nudge_on(slug, game):
    b, m = boards.get_board(g.db, slug, g.person)
    boards.set_nudge(g.db, b, g.person, game, True)
    g.db.commit()
    return jsonify(boards.board_json(g.db, b, m))


@api.put("/boards/<slug>/nudges")
@auth_required
def nudges_on(slug):
    """Every game on your agenda here nudges before it resets."""
    b, m = boards.get_board(g.db, slug, g.person)
    boards.set_nudges(g.db, b, g.person, True)
    g.db.commit()
    return jsonify(boards.board_json(g.db, b, m))


@api.delete("/boards/<slug>/nudges")
@auth_required
def nudges_off(slug):
    b, m = boards.get_board(g.db, slug, g.person)
    boards.set_nudges(g.db, b, g.person, False)
    g.db.commit()
    return jsonify(boards.board_json(g.db, b, m))


@api.delete("/boards/<slug>/agenda/<game>/nudge")
@auth_required
def nudge_off(slug, game):
    b, m = boards.get_board(g.db, slug, g.person)
    boards.set_nudge(g.db, b, g.person, game, False)
    g.db.commit()
    return jsonify(boards.board_json(g.db, b, m))


# -- filing ----------------------------------------------------------------------

PASTE_CHARS = 16_000  # a day's worth of shares is a few hundred; chat imports use the script
PASTES_A_DAY = 300


def _paste_text() -> str:
    text = body().get("text")
    if not isinstance(text, str) or not text.strip():
        fail(400, "paste something first")
    if len(text) > PASTE_CHARS:
        fail(413, f"that's a long paste. send at most {PASTE_CHARS:,} characters at a time.")
    throttle.limit(g.db, f"paste:{g.person.id}", PASTES_A_DAY, 86400, "the clerk has read enough for today. try again tomorrow.")
    return text


HELD = timedelta(days=1)  # how far back a result held on a phone may say it was pasted


def _pasted_at(now: datetime) -> datetime:
    """When a result held on a phone (offline, or the server restarting) was pasted, so
    one held across a reset isn't filed late. Anything odd, or older than a day, is now."""
    v = body().get("pasted_at")
    try:
        at = datetime.fromisoformat(v.replace("Z", "+00:00")) if isinstance(v, str) else None
    except ValueError:
        return now
    return at if at and at.tzinfo and now - HELD <= at <= now else now


@api.post("/pastes")
@auth_required
def paste():
    text = _paste_text()
    source = "share" if body().get("source") == "share" else "paste"  # "import" is internal
    f = filing.file_paste(g.db, g.person, text, now=_pasted_at(clock() or utcnow()), source=source)
    g.db.commit()
    return jsonify(f.to_dict()), 201


@api.post("/pastes/preview")
@auth_required
def paste_preview():
    """What filing this paste would do, without keeping any of it: the app shows it
    and files only when the person says save."""
    text = _paste_text()
    sp = g.db.begin_nested()
    f = filing.file_paste(g.db, g.person, text)
    out = f.to_dict()
    for ev in out["events"]:
        row = ev["result_id"] and g.db.get(Result, ev["result_id"])
        ev["outcome"], ev["metrics"] = (row.outcome, dict(row.metrics)) if row and ev["kind"] != "conflict" else (None, {})
        if ev["kind"] != "conflict":
            ev["result_id"] = None  # those rows aren't kept
    out["paste_id"] = None
    sp.rollback()
    g.db.rollback()
    return jsonify(out)


# -- the phone shortcut ----------------------------------------------------------
# iPhones have no share target for web apps, so a Shortcut in the share sheet posts the
# share text here with a key of its own. The key only files: it can't read or change
# anything else, and making a new one retires the old.

def _shortcut_key(s, person: Person) -> AuthToken | None:
    return s.scalar(select(AuthToken).where(AuthToken.person_id == person.id, AuthToken.scope == "shortcut"))


@api.get("/me/shortcut")
@auth_required
def shortcut_status():
    k = _shortcut_key(g.db, g.person)
    return jsonify({"set": k is not None, "used": k.last_seen.isoformat() if k and k.last_seen > k.created_at else None})


@api.post("/me/shortcut")
@auth_required
def shortcut_new():
    """A new shortcut key, shown this once; any old one stops working."""
    old = _shortcut_key(g.db, g.person)
    if old:
        g.db.delete(old)
    key = auth.issue_token(g.db, g.person, device="phone shortcut", scope="shortcut")
    g.db.commit()
    return jsonify({"key": key}), 201


@api.delete("/me/shortcut")
@auth_required
def shortcut_off():
    old = _shortcut_key(g.db, g.person)
    if old:
        g.db.delete(old)
        g.db.commit()
    return jsonify({"set": False})


def _said(f: filing.Filing, person: Person, s) -> str:
    """The filing in a line or two, for the shortcut's notification."""
    name = lambda gid: REGISTRY[gid].name if gid in REGISTRY else gid
    playing = set(s.scalars(select(Agenda.game_id).where(Agenda.person_id == person.id)))
    lines = []
    for e in f.events:
        lines.append({
            "filed": f"filed {name(e.game)} {e.puzzle}{' (late)' if e.late else ''}"
                     + ("" if e.game in playing else ". it's not on your agenda yet: add it in the app"),
            "merged": f"added the {', '.join(e.added)} to {name(e.game)} {e.puzzle}",
            "duplicate": f"{name(e.game)} {e.puzzle} was already in the minutes",
            "not_out_yet": f"{name(e.game)} {e.puzzle} isn't out yet",
            "conflict": f"{name(e.game)} {e.puzzle} is already filed, with a different result. paste it in the app to pick one",
        }.get(e.kind, f"{name(e.game)} {e.puzzle}"))
    lines += [f"we can't read {u['name']} yet. the clerk has asked for a parser." for u in f.unknown]
    return "\n".join(lines) or "nothing readable in that. share the result text the game gives you."


@api.post("/shortcut")
def shortcut_file():
    """{key, text}, or the key as a bearer token: files the text at once and answers in
    plain words (errors too), which the shortcut shows as a notification."""
    try:
        b = body()
        key = b.get("key") if isinstance(b.get("key"), str) else auth.bearer()
        row = auth.token_row(g.db, key.strip())
        if row is None:
            throttle.limit(g.db, f"shortcut:{throttle.caller()}", 20, 3600, "too many wrong keys from here. try again in an hour.")
            fail(401, "that key doesn't work any more. make a new one in boredroom: you, everywhere, iphone shortcut.")
        row.last_seen = utcnow()
        g.person = row.person
        f = filing.file_paste(g.db, g.person, _paste_text(), now=clock() or utcnow(), source="share")
        said = _said(f, g.person, g.db)
        g.db.commit()
        return Response(said, 201, mimetype="text/plain")
    except ApiError as e:
        return Response(e.description, e.code, mimetype="text/plain")


@api.get("/results")
@auth_required
def my_results():
    q = select(Result).where(Result.person_id == g.person.id)
    if request.args.get("game"):
        q = q.where(Result.game_id == request.args["game"])
    if request.args.get("puzzle"):
        q = q.where(Result.puzzle_key == request.args["puzzle"])
    rows = g.db.scalars(q.order_by(Result.filed_at.desc()).limit(200))
    return jsonify([filing.result_json(r) for r in rows])


@api.post("/results/<int:rid>/replace")
@auth_required
def replace(rid):
    pid = body().get("paste_id")
    if not isinstance(pid, int):
        fail(400, "say which paste replaces it (paste_id)")
    row = filing.replace(g.db, g.person, rid, pid)
    g.db.commit()
    return jsonify(filing.result_json(row))


@api.delete("/results/<int:rid>")
@auth_required
def withdraw(rid):
    row = filing.withdraw(g.db, g.person, rid)
    g.db.commit()
    return jsonify(filing.result_json(row))
