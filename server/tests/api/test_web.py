from boredroom.app import create_app
from boredroom.config import Config


def test_web_app_is_served_with_a_fallback(tmp_path, engine):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "assets" / "app-1a2b.js").write_text("// js")
    c = create_app(Config(web_dist=str(tmp_path)), engine=engine).test_client()
    page = c.get("/")
    assert page.data == b"<div id=root></div>"
    assert "script-src 'self'" in page.headers["Content-Security-Policy"] and "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]
    assert c.get("/b/soup/m/wiki").data == b"<div id=root></div>"  # the app routes itself
    js = c.get("/assets/app-1a2b.js")
    assert js.data == b"// js" and "immutable" in js.headers["Cache-Control"]
    assert c.get("/api/v1/nope").status_code == 404 and c.get("/api/v1/nope").is_json
    assert c.get("/../pyproject.toml").data == b"<div id=root></div>"
    assert c.get("/privacy").status_code == 200  # blueprints win over the fallback


HEAD = ('<title>boredroom</title><meta name="description" content="generic" />'
        '<meta property="og:title" content="boredroom · your group chat has a board" /><meta property="og:description" content="generic" />'
        '<meta property="og:image" content="https://boredroom.shmk.dev/og.png" />'
        '<meta property="og:url" content="https://boredroom.shmk.dev/" />')


def test_an_invite_link_previews_who_saved_the_seat(tmp_path, engine, seat):
    (tmp_path / "index.html").write_text(HEAD)
    (tmp_path / "og.png").write_bytes(b"generic png")
    code = seat("alice").post("/boards", {"name": "soup"}).json["invite"]["code"]
    c = create_app(Config(web_dist=str(tmp_path)), engine=engine).test_client()
    page = c.get(f"/join/{code}", headers={"Host": "stage.example"}).text
    assert 'og:title" content="alice saved you a seat"' in page
    assert f'og:image" content="https://stage.example/og/invite/{code}.png"' in page
    assert "boredroom.shmk.dev" not in page
    png = c.get(f"/og/invite/{code}.png")
    assert png.mimetype == "image/png" and png.data[:4] == b"\x89PNG"
    assert c.get("/og/invite/smug-walrus-nopes.png").data == b"generic png"
    dead = c.get("/join/smug-walrus-nopes").text  # a dead invite previews as plain boredroom
    assert 'og:title" content="boredroom · ' in dead and "/og/invite/" not in dead
