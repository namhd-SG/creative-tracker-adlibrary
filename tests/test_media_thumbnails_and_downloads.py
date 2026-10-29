"""Media fields, thumbnails, expired-link refresh and zip — no network (fetch is faked)."""
import json
import sqlite3
import time
import urllib.error
import zipfile
from pathlib import Path

import pytest

from ctal import media_download as md
from ctal import storage
from ctal.parse_ad_library_payload import ad_from_node
from ctal.thumbnails import save_thumbnails, thumb_path

FX = Path(__file__).parent / "fixtures"


def real_ad():
    return ad_from_node(json.loads((FX / "ad-node-with-video-vidix.json").read_text()))


def test_real_node_has_video_and_preview():
    ad = real_ad()
    assert ad.kind == "video"
    assert ad.video_url.startswith("https://") and ".mp4" in ad.video_url
    assert ad.video_sd_url and ad.thumb_url
    assert md.expires_at(ad.video_url) > 1_700_000_000        # oe=<hex epoch> is readable


def test_old_database_gets_media_columns(tmp_path):
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)                                   # schema of the first release
    con.executescript("""CREATE TABLE ads (ad_archive_id TEXT PRIMARY KEY, page_id TEXT NOT NULL, page_name TEXT,
      start_day TEXT NOT NULL, end_day TEXT, is_active INTEGER NOT NULL, collation_id TEXT, collation_count INTEGER,
      display_format TEXT, link_url TEXT, destination TEXT, body TEXT, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL);
      INSERT INTO ads VALUES ('1','9','P','2026-10-20',NULL,1,NULL,1,'VIDEO',NULL,NULL,NULL,'t','t');""")
    con.commit()
    con.close()
    con = storage.connect(db)
    cols = {r[1] for r in con.execute("PRAGMA table_info(ads)")}
    assert {"video_url", "thumb_url", "kind"} <= cols
    assert storage.load_ads(con, "9")[0].kind == "video"
    ad = real_ad()
    storage.upsert_ads(con, [ad])
    assert storage.load_ad(con, ad.ad_archive_id).video_url == ad.video_url


def test_thumbnails_saved_once(tmp_path):
    ad = real_ad()
    calls = []
    res = save_thumbnails([ad], tmp_path, fetch=lambda u: calls.append(u) or b"\xff\xd8jpeg", pause=0)
    assert (res.saved, res.already) == (1, 0) and thumb_path(tmp_path, ad.ad_archive_id).exists()
    res = save_thumbnails([ad], tmp_path, fetch=lambda u: calls.append(u) or b"x", pause=0)
    assert (res.saved, res.already) == (0, 1) and len(calls) == 1      # never re-downloads


def test_thumbnail_failure_is_counted_not_raised(tmp_path):
    def boom(_):
        raise urllib.error.HTTPError("u", 410, "Gone", None, None)
    res = save_thumbnails([real_ad()], tmp_path, fetch=boom, pause=0)
    assert (res.saved, res.failed) == (0, 1)


def with_link(ad, oe_epoch):
    ad.video_url = ad.video_url.split("oe=")[0] + f"oe={oe_epoch:X}&x=1"
    return ad


@pytest.fixture
def db(tmp_path):
    con = storage.connect(tmp_path / "t.db")
    return con


def test_stale_link_rescans_page_then_downloads(db):
    ad = with_link(real_ad(), int(time.time()) - 3600)          # expired an hour ago
    storage.upsert_ads(db, [ad])
    refreshed = []

    def refresh(page_id):                                       # what a rescan does: store a fresh link
        refreshed.append(page_id)
        storage.upsert_ads(db, [with_link(real_ad(), int(time.time()) + 3 * 86400)])

    got, data = md.fetch_media(db, ad.ad_archive_id, refresh, fetch=lambda u: b"mp4:" + u.encode())
    assert refreshed == [ad.page_id]
    assert not md.is_stale(got.video_url) and data.startswith(b"mp4:")


def test_link_dead_before_expiry_gets_one_retry(db):
    ad = with_link(real_ad(), int(time.time()) + 86400)
    storage.upsert_ads(db, [ad])
    calls, refreshed = [], []

    def fetch(u):
        calls.append(u)
        if len(calls) == 1:
            raise urllib.error.HTTPError(u, 403, "Forbidden", None, None)
        return b"ok"
    _, data = md.fetch_media(db, ad.ad_archive_id, refreshed.append, fetch=fetch)
    assert data == b"ok" and refreshed == [ad.page_id] and len(calls) == 2


def test_fresh_link_is_not_rescanned(db):
    ad = with_link(real_ad(), int(time.time()) + 86400)
    storage.upsert_ads(db, [ad])
    md.fetch_media(db, ad.ad_archive_id, lambda p: pytest.fail("must not rescan"), fetch=lambda u: b"ok")


def test_zip_names_failures_and_single_rescan(db, tmp_path):
    a = with_link(real_ad(), int(time.time()) - 10)
    storage.upsert_ads(db, [a])
    refreshed = []
    dest = tmp_path / "x.zip"
    ok, failed = md.write_zip(db, [(a.ad_archive_id, "app_page_2026-10-22_1.mp4"), (a.ad_archive_id, "app_page_2026-10-22_1.mp4"),
                                   ("999", "missing.mp4")], dest, refreshed.append, fetch=lambda u: b"data")
    assert (ok, failed) == (2, ["999"])
    assert refreshed == [a.page_id]                              # one rescan per page, not per file
    with zipfile.ZipFile(dest) as z:
        assert z.namelist() == ["app_page_2026-10-22_1.mp4", "app_page_2026-10-22_1-2.mp4"]
        assert z.infolist()[0].compress_type == zipfile.ZIP_STORED
