"""The local web server end to end on a random 127.0.0.1 port (network to Facebook is faked)."""
import json
import threading
import time
import urllib.error
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from ctal import competitor_list as cl
from ctal import media_download, storage
from ctal.parse_ad_library_payload import PageInfo, ad_from_node
from ctal.web_server import App, make_server

FX = Path(__file__).parent / "fixtures"
AL = "https://www.facebook.com/ads/library/?active_status=all&view_all_page_id={}"


@pytest.fixture
def site(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    node = json.loads((FX / "ad-node-with-video-vidix.json").read_text())
    ad = ad_from_node(node)
    ad.start_day = time.strftime("%Y-%m-%d")                     # inside the 14-day window
    ad.video_url = ad.video_url.split("oe=")[0] + f"oe={int(time.time()) + 86400:X}"
    db = tmp_path / "data" / "tracker.db"
    con = storage.connect(db)
    storage.upsert_ads(con, [ad])
    storage.save_page(con, PageInfo(ad.page_id, ad.page_name, owner="Owner Co"), AL.format(ad.page_id),
                      {"at": "2026-10-29T08:00:00+00:00", "coverage": 1.0, "collected": 1, "shown_total": 1, "warnings": []})
    entries = []
    cl.add_app(entries, "Vidix", "https://play.google.com/store/apps/details?id=com.vidix.aivideogenerator.aiphotogenerator")
    cl.add_page(entries, "Vidix", AL.format(ad.page_id))
    cl.save(entries, tmp_path / "doi_thu.csv")
    (tmp_path / "data" / "thumbs").mkdir()
    (tmp_path / "data" / "thumbs" / f"{ad.ad_archive_id}.jpg").write_bytes(b"\xff\xd8jpeg")
    monkeypatch.setattr(media_download, "http_get", lambda u, timeout=30: b"VIDEO-BYTES")
    app = App(db, tmp_path / "doi_thu.csv", tmp_path / "out")
    srv = make_server(app, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", ad, app, tmp_path
    srv.shutdown()


def get(url):
    with urllib.request.urlopen(url) as r:
        return r.status, r.headers, r.read()


def post(url, body):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def test_binds_loopback_only(site):
    base, *_ = site
    assert base.startswith("http://127.0.0.1:")


def test_page_and_library(site):
    base, ad, *_ = site
    code, _, html = get(base + "/")
    assert code == 200 and "🎬 Thư viện" in html.decode() and "🏢 Đối thủ" in html.decode()
    lib = json.loads(get(base + "/api/library")[2])
    card = lib["cards"][0]
    assert card["ad_id"] == ad.ad_archive_id and card["app"] == "Vidix" and card["kind"] == "video"
    assert card["thumb"] == f"/thumbs/{ad.ad_archive_id}.jpg"
    assert card["file"].startswith("vidix_") and card["file"].endswith(f"_{ad.ad_archive_id}.mp4")
    assert get(base + card["thumb"])[2] == b"\xff\xd8jpeg"


def test_competitors_and_adding_writes_csv(site):
    base, ad, app, tmp = site
    comp = json.loads(get(base + "/api/competitors")[2])
    page = comp["apps"][0]["pages"][0]
    assert page["owner"] == "Owner Co" and page["scan"]["coverage"] == 1.0
    assert json.loads(post(base + "/api/apps", {"name": "Hailuo AI", "link_store": "https://play.google.com/store/apps/details?id=ai.hailuo.video"})[2])["status"] == "đã thêm"
    r = json.loads(post(base + "/api/pages", {"app": "hailuo ai", "link": AL.format("722059307667326"), "note": "page chính"})[2])
    assert r == {"status": "đã thêm", "page_id": "722059307667326"}
    rows = cl.load(tmp / "doi_thu.csv")
    assert [(e.app, e.page_id, e.ghi_chu) for e in rows][-1] == ("Hailuo AI", "722059307667326", "page chính")
    assert post(base + "/api/pages", {"app": "Không có", "link": "123456"})[0] == 400


def test_download_one_and_zip(site):
    base, ad, *_ = site
    code, headers, data = get(base + f"/api/download/{ad.ad_archive_id}")
    assert code == 200 and data == b"VIDEO-BYTES"
    assert f"_{ad.ad_archive_id}.mp4" in headers["Content-Disposition"]
    code, headers, data = post(base + "/api/zip", {"ids": [ad.ad_archive_id, "404404"]})
    assert code == 200 and headers["X-Failed"] == "404404"
    assert zipfile.ZipFile(BytesIO(data)).read(zipfile.ZipFile(BytesIO(data)).namelist()[0]) == b"VIDEO-BYTES"


def test_media_redirects_to_fresh_link(site):
    base, ad, *_ = site

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.build_opener(NoRedirect).open(base + f"/api/media/{ad.ad_archive_id}")
    assert e.value.code == 302 and e.value.headers["Location"].startswith("https://")


def test_scan_endpoints_queue_pages_and_stop(site, monkeypatch):
    base, ad, app, _ = site
    release, seen = threading.Event(), []

    def fake_run(item, on_progress):                     # stands in for the child `ctal scan` process
        seen.append(item["key"])
        on_progress({"collected": 3, "total": 9, "scrolls": 1})
        release.wait(5)
        return {"page_id": item["key"], "collected": 9, "shown_total": 9, "coverage": 1.0}
    monkeypatch.setattr(app.scans, "_run_page", fake_run)
    app.scans.pause = (0, 0)
    code, _, body = post(base + "/api/scan", {"app": "Vidix"})
    r = json.loads(body)
    assert code == 200 and r["added"] == 1 and r["running"]
    for _ in range(100):
        st = json.loads(get(base + "/api/scan")[2])
        if st["pages"].get(ad.page_id, {}).get("status") == "running":
            break
        time.sleep(0.02)
    assert st["pages"][ad.page_id]["collected"] == 3 and st["current_page"]["app"] == "Vidix"
    assert json.loads(post(base + "/api/scan", {"key": ad.page_id})[2])["added"] == 0   # already running
    assert post(base + "/api/scan", {"app": "Không có"})[0] == 400
    release.set()
    for _ in range(100):
        st = json.loads(get(base + "/api/scan")[2])
        if not st["running"]:
            break
        time.sleep(0.02)
    assert st["pages"][ad.page_id]["status"] == "done" and seen == [ad.page_id]
    assert json.loads(post(base + "/api/scan/stop", {})[2])["running"] is False


def test_scan_window_comes_from_the_page_date_filter(site, monkeypatch):
    from datetime import date, timedelta
    base, ad, app, _ = site
    got = []
    monkeypatch.setattr(app.scans, "_run_page", lambda item, on_progress: got.append(item) or
                        {"page_id": item["key"], "collected": 1, "shown_total": 1, "coverage": 1.0})
    app.scans.pause = (0, 0)
    since = (date.today() - timedelta(days=45)).isoformat()
    r = json.loads(post(base + "/api/scan", {"app": "Vidix", "since": since})[2])
    assert r["since"] == since and r["days"] == 45
    for _ in range(100):
        if got:
            break
        time.sleep(0.02)
    assert got[0]["days"] == 45
    cmd = app.scans._cmd(got[0]["target"], "--progress", days=got[0]["days"])
    assert cmd[cmd.index("--days") + 1] == "45"                  # what the child `ctal scan` receives
    assert post(base + "/api/scan", {"app": "Vidix", "since": "29-10-2026"})[0] == 400


def test_api_window_follows_the_date_filter(site):
    from datetime import date, timedelta
    base, ad, app, _ = site
    con = storage.connect(app.db)
    old = storage.load_ad(con, ad.ad_archive_id)
    old.ad_archive_id, old.collation_id = "777000777", None
    old.start_day = (date.today() - timedelta(days=40)).isoformat()   # outside the default 14 days
    storage.upsert_ads(con, [old])
    default = json.loads(get(base + "/api/library")[2])
    assert "777000777" not in {c["ad_id"] for c in default["cards"]}
    since = (date.today() - timedelta(days=60)).isoformat()
    wide = json.loads(get(base + f"/api/library?since={since}")[2])
    assert "777000777" in {c["ad_id"] for c in wide["cards"]}
    assert wide["since"] == since and wide["today"] == date.today().isoformat()
    comp = json.loads(get(base + f"/api/competitors?since={since}")[2])
    assert len(comp["apps"][0]["days"]) == 61
    y = (date.today() - timedelta(days=1)).isoformat()
    narrow = json.loads(get(base + f"/api/competitors?since={y}&until={y}")[2])
    assert len(narrow["apps"][0]["days"]) >= 15        # tiles still get the last 14 days
