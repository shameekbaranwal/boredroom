"""JSON API, /api/v1. See docs/SERVER.md part 5.

Handlers commit; services (filing, boards) only flush.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import select

from . import boards, claims, filing, reads
from . import auth
from .auth import auth_required, create_guest, valid_tz, USERNAME
from .errors import fail
from .models import Membership, Person, Result
from .parser import REGISTRY

api = Blueprint("api", __name__, url_prefix="/api/v1")


def body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    if data is None:
        return {}
    if not isinstance(data, dict):
        fail(400, "send a json object")
    return data


def me_json(p: Person) -> dict[str, Any]:
    live = [m for m in p.memberships if m.left_at is None]
    return {
        "username": p.username, "kind": p.kind, "tz": p.tz, "email": p.email,
        "boards": [{"slug": m.board.slug, "name": m.board.name, "nickname": m.nickname, "role": m.role}
                   for m in sorted(live, key=lambda m: m.board.name)],
    }


# -- people ----------------------------------------------------------------------

@api.post("/guests")
def new_guest():
    b = body()
    tz = b.get("tz") or current_app.config["BOREDROOM"].default_tz
    person, token = create_guest(g.db, b.get("username"), tz, request.headers.get("User-Agent", "")[:200])
    g.db.commit()
    return jsonify({"token": token, "me": me_json(person)}), 201


@api.get("/config")
def client_config():
    """What a client needs before signing in. The google client id is public by design."""
    return jsonify({"google_client_id": current_app.config["BOREDROOM"].google_client_id})


@api.post("/auth/google")
def google_sign_in():
    """{credential: <google id token>, tz?}. Signed in as a guest, the seat becomes the
    account (history kept); otherwise it signs in to, or creates, the google account."""
    client_id = current_app.config["BOREDROOM"].google_client_id
    if not client_id:
        fail(503, "google sign-in isn't set up on this server")
    b = body()
    credential = b.get("credential")
    if not isinstance(credential, str) or not credential:
        fail(400, "send the google credential")
    verify = current_app.config.get("GOOGLE_VERIFY", auth.verify_google)  # swapped in tests
    who = verify(credential, client_id)
    row = auth.token_row(g.db, auth.bearer())
    tz = b.get("tz") or current_app.config["BOREDROOM"].default_tz
    person, token, created = auth.sign_in_google(
        g.db, who, tz, row.person if row else None, request.headers.get("User-Agent", "")[:200])
    g.db.commit()
    return jsonify({"token": token, "created": created, "me": me_json(person)}), 201 if created else 200


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
        if not valid_tz(b["tz"]):
            fail(400, f"unknown timezone {b['tz']}")
        g.person.tz = b["tz"]
    if "username" in b:
        name = str(b["username"]).strip().lower()
        if not USERNAME.match(name):
            fail(400, "usernames are 2–30 characters: letters, digits, . _ -")
        if name != g.person.username and g.db.scalar(select(Person.id).where(Person.username == name)):
            fail(409, "that username is taken")
        g.person.username = name
    g.db.commit()
    return jsonify(me_json(g.person))


# -- the library -----------------------------------------------------------------

@api.get("/games")
def games():
    return jsonify([{"id": c.id, "name": c.name, "key": c.key, "ranked": c.ranked(),
                     "links": list(c.links), "ranker": list(c.ranker),
                     "metrics": [{"name": m.name, "kind": m.kind, "better": m.better, "max": m.max,
                                  "unit": m.unit} for m in c.metrics]}
                    for c in sorted(REGISTRY.values(), key=lambda c: c.name) if not c.ignore])


# -- boards ----------------------------------------------------------------------

@api.post("/boards")
@auth_required
def new_board():
    board = boards.create_board(g.db, g.person, str(body().get("name", "")))
    g.db.commit()
    m = g.db.get(Membership, (board.id, g.person.id))
    return jsonify(boards.board_json(g.db, board, m)), 201


@api.post("/boards/join")
@auth_required
def join_board():
    board = boards.join(g.db, g.person, str(body().get("code", "")))
    g.db.commit()
    m = g.db.get(Membership, (board.id, g.person.id))
    return jsonify(boards.board_json(g.db, board, m))


@api.get("/boards/<slug>")
@auth_required
def board(slug):
    b, m = boards.get_board(g.db, slug, g.person)
    return jsonify(boards.board_json(g.db, b, m))


@api.patch("/boards/<slug>/me")
@auth_required
def board_me(slug):
    b, m = boards.get_board(g.db, slug, g.person)
    nick = str(body().get("nickname", "")).strip().lower()
    if not 1 <= len(nick) <= 40:
        fail(400, "nicknames are 1–40 characters")
    m.nickname = nick
    g.db.commit()
    return jsonify(boards.board_json(g.db, b, m))


@api.get("/boards/<slug>/today")
@auth_required
def board_today(slug):
    board, _ = boards.get_board(g.db, slug, g.person)
    return jsonify(reads.today(g.db, board, g.person))


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


# -- filing ----------------------------------------------------------------------

@api.post("/pastes")
@auth_required
def paste():
    text = body().get("text")
    if not isinstance(text, str) or not text.strip():
        fail(400, "paste something first")
    source = "share" if body().get("source") == "share" else "paste"  # "import" is internal
    f = filing.file_paste(g.db, g.person, text, source=source)
    g.db.commit()
    return jsonify(f.to_dict()), 201


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
