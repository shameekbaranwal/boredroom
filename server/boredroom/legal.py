"""/privacy and /terms: the URLs Google sign-in's consent screen links to. Served by
the demo now and the app later, so the URLs never change."""
from __future__ import annotations

import os
from html import escape
from pathlib import Path

from flask import Blueprint, Response

legal = Blueprint("legal", __name__)
TEMPLATE = (Path(__file__).parent / "pages" / "legal.html").read_text(encoding="utf-8")
UPDATED = "31 october 2026"


def _contact() -> str:
    email = os.environ.get("BOREDROOM_CONTACT_EMAIL")
    if email:
        return f'email <a href="mailto:{escape(email)}">{escape(email)}</a>'
    return "message the person who runs it"


def _page(title: str, body: str) -> Response:
    html = TEMPLATE.replace("{{ title }}", escape(title)).replace("{{ body }}", body)
    return Response(html, mimetype="text/html")


@legal.get("/privacy")
def privacy():
    return _page("privacy policy", f"""
<h1>privacy policy</h1>
<p class="muted">last updated {UPDATED}</p>
<p>boredroom is a small leaderboard for friends who play daily puzzle games. it's run by one
person as a hobby, not by a company. this page says what it keeps and why.</p>

<h2>what boredroom keeps</h2>
<ul>
<li><b>your google account basics</b>, if you sign in with google: your name, email address and
google's account id for you. nothing else from your google account; boredroom can't see your
mail, contacts or files.</li>
<li><b>what you paste</b>: the game results you file, exactly as pasted, and what's read from
them (scores, grids, and anything else in the share text, such as a wiki game route).</li>
<li><b>your boredroom details</b>: your username, nicknames on boards, the boards you're on, the
games on your agenda, and your timezone.</li>
<li><b>basic server logs</b> (time, page requested, ip address), kept for a short time to keep the
service running and find problems.</li>
</ul>

<h2>who can see it</h2>
<ul>
<li>members of a board you're on see your nickname and your results for the games on your
agenda there. gameplay details and spoilers are shown to a member only after they've filed the
same puzzle.</li>
<li>your email address is never shown to other members.</li>
<li>nothing is sold, shared with advertisers, or used for ads. there are no third-party
analytics or trackers.</li>
</ul>

<h2>where it's stored</h2>
<p>on a server run by boredroom's operator in india, behind cloudflare (which carries the traffic
but doesn't store your data). google handles sign-in under
<a href="https://policies.google.com/privacy">google's privacy policy</a>.</p>

<h2>keeping and deleting</h2>
<p>your data stays while you use boredroom. to see what's stored about you, or to have your
account and results deleted, {_contact()}. it will be done within 30 days.</p>

<h2>changes</h2>
<p>if this policy changes, the date at the top changes too. big changes will be announced in
the app.</p>
""")


@legal.get("/terms")
def terms():
    return _page("terms", f"""
<h1>terms</h1>
<p class="muted">last updated {UPDATED}</p>
<p>boredroom is a free hobby project for friends. by using it you agree to this:</p>
<ul>
<li>it's provided as is, with no guarantees. it may change, break, lose data or shut down.</li>
<li>paste only your own results, and don't use it to harass anyone or to break the law.</li>
<li>boredroom isn't affiliated with the games it tracks; their names belong to their owners.</li>
<li>accounts that misuse it can be removed.</li>
</ul>
<p>questions: {_contact()}. see also the <a href="/privacy">privacy policy</a>.</p>
""")
