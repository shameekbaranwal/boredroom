from boredroom.app import create_app
from boredroom.config import Config


def test_web_app_is_served_with_a_fallback(tmp_path, engine):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "assets" / "app-1a2b.js").write_text("// js")
    c = create_app(Config(web_dist=str(tmp_path)), engine=engine).test_client()
    assert c.get("/").data == b"<div id=root></div>"
    assert c.get("/b/soup/m/wiki").data == b"<div id=root></div>"  # the app routes itself
    js = c.get("/assets/app-1a2b.js")
    assert js.data == b"// js" and "immutable" in js.headers["Cache-Control"]
    assert c.get("/api/v1/nope").status_code == 404 and c.get("/api/v1/nope").is_json
    assert c.get("/../pyproject.toml").data == b"<div id=root></div>"
    assert c.get("/privacy").status_code == 200  # blueprints win over the fallback
