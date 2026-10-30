def test_privacy_and_terms_pages(client):
    for path in ("/privacy", "/terms"):
        r = client.get(path)
        assert r.status_code == 200 and r.mimetype == "text/html"
        assert b"{{" not in r.data
