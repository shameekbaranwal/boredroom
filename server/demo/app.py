"""Paste-box demo for the parser. TEMPORARY: an early demo for friends, deployed
until the real web app replaces it (see build/README.md).

    cd server && uv run python demo/app.py [--host 0.0.0.0] [--port 5077]

In the container it runs under gunicorn (see Dockerfile), published on port 5077.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request, send_file

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from boredroom.parser import REGISTRY, forward_text, merge, parse  # noqa: E402
from boredroom.parser import games  # noqa: E402,F401
from boredroom.parser.forward import PADDING  # noqa: E402
from boredroom.legal import legal  # noqa: E402

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 256 * 1024  # it's public: pastes are small
HERE = Path(__file__).resolve().parent
MAX_PASTES = 100
app.register_blueprint(legal)  # /privacy and /terms, kept when the app replaces the demo


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def index():
    return send_file(HERE / "index.html")


@app.get("/api/games")
def list_games():
    now = datetime.now(timezone.utc)
    tz = request.args.get("tz", "Asia/Kolkata")
    out = []
    for g in REGISTRY.values():
        if g.ignore:
            continue
        cur = g.current(now, tz)
        out.append({
            "id": g.id, "name": g.name, "key": g.key, "ranked": g.ranked(),
            "current": cur.isoformat() if hasattr(cur, "isoformat") else cur,
            "reset": f"{g.reset.at:%H:%M} {g.reset.tz or 'local'}",
            "ranker": [{"metric": m, "better": g.metric_def(m).better} for m in g.ranker],
        })
    return jsonify(sorted(out, key=lambda x: x["name"]))


def _when(body):
    tz = body.get("tz") or "Asia/Kolkata"
    now = datetime.fromisoformat(body["now"]) if body.get("now") else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo(tz))
    return now, tz


def _view(r):
    d = r.to_dict()
    d["name"] = REGISTRY[r.game].name
    d["forward"] = forward_text(r).replace(PADDING, "[4000 invisible characters]")
    d["units"] = {m.name: m.unit for m in REGISTRY[r.game].metrics if m.unit}
    return d


@app.post("/api/parse")
def api_parse():
    body = request.get_json(force=True)
    now, tz = _when(body)
    parsed = parse(body.get("text", ""), now=now, tz=tz)
    out = parsed.to_dict()
    out["results"] = [_view(r) for r in parsed.results]
    return jsonify(out)


@app.post("/api/file")
def api_file():
    """Replays one member's pastes in order, the way filing will work: a repeat of a
    puzzle merges, is ignored as a duplicate, or asks to replace. `replace` holds the
    member's answers to those prompts, keyed by paste index."""
    body = request.get_json(force=True)
    now, tz = _when(body)
    answers = body.get("replace", {})
    filed, events = {}, []
    for i, text in enumerate(body.get("pastes", [])[:MAX_PASTES]):
        for r in parse(text, now=now, tz=tz).results:
            key = (r.game, str(r.puzzle))
            ev = {"paste": i, "game": REGISTRY[r.game].name, "puzzle": str(r.puzzle), "added": []}
            if key not in filed:
                filed[key] = r
                ev["kind"] = "filed"
            else:
                m = merge(filed[key], r)
                ev["kind"], ev["added"] = m.kind, m.added
                if m.kind == "enrich":
                    filed[key] = m.result
                elif m.kind == "conflict":
                    ev["answer"] = answers.get(str(i))
                    if ev["answer"] == "replace":
                        r.warnings.append("amended")
                        filed[key] = r
            events.append(ev)
    return jsonify({"filed": [_view(r) for r in filed.values()], "events": events})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5077)
    a = ap.parse_args()
    app.run(host=a.host, port=a.port, debug=False)
