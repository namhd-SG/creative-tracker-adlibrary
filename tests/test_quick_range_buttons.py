"""'Hôm nay' / 'Hôm qua' quick ranges: the page sets the right window and scans from the right day."""
import json
import time
from datetime import timedelta

import pytest
from playwright.sync_api import sync_playwright

from ctal import storage
from ctal.parse_ad_library_payload import ad_library_today

from test_web_server_endpoints import get, post, site  # noqa: F401  (shared live-server fixture)


def test_yesterday_scan_and_window_on_the_server(site, monkeypatch):
    base, ad, app, _ = site
    today = ad_library_today()
    yday = (today - timedelta(days=1)).isoformat()
    con = storage.connect(app.db)
    y = storage.load_ad(con, ad.ad_archive_id)
    y.ad_archive_id, y.collation_id, y.start_day = "555000555", None, yday
    storage.upsert_ads(con, [y])                                  # one creative yesterday, one today
    got = []
    monkeypatch.setattr(app.scans, "_run_page", lambda item, cb: got.append(item) or
                        {"page_id": item["key"], "collected": 1, "shown_total": 1, "coverage": 1.0})
    app.scans.pause = (0, 0)
    r = json.loads(post(base + "/api/scan", {"app": "Vidix", "since": yday})[2])
    assert (r["since"], r["days"]) == (yday, 1)                   # "có hiển thị từ hôm qua"
    lib = json.loads(get(base + f"/api/library?since={yday}&until={yday}")[2])
    assert [c["ad_id"] for c in lib["cards"]] == ["555000555"]   # only ads that STARTED yesterday
    assert post(base + "/api/scan", {"key": "nope", "since": today.isoformat()})[0] == 400   # unknown page
    lib = json.loads(get(base + f"/api/library?since={today}&until={today}")[2])
    assert "555000555" not in {c["ad_id"] for c in lib["cards"]}


@pytest.fixture
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def test_quick_range_chips_in_the_page(site, browser):
    base, ad, app, _ = site
    today = ad_library_today()
    yday = (today - timedelta(days=1)).isoformat()
    page = browser.new_page()
    requests = []
    page.on("request", lambda r: requests.append((r.url, r.post_data)))
    page.goto(base + "/")
    page.wait_for_function("document.querySelector('#fFrom').value !== ''")
    page.click('#tabs a[data-v="comp"]')

    page.click('#rangeChips [data-range="yday"]')
    page.wait_for_function(f"document.querySelector('#fFrom').value === '{yday}'")
    page.wait_for_selector('#rangeChips [data-range="yday"].on')
    assert page.input_value("#fTo") == yday
    assert any(f"since={yday}&until={yday}" in u for u, _ in requests if "/api/library" in u)
    assert f"trong khoảng {yday[8:10]}/{yday[5:7]} → hôm nay" in page.inner_text("#scanRange")
    assert page.locator('#rangeChips [data-range="yday"]').get_attribute("class") == "chip on"
    assert page.is_hidden("#laNote")                              # yesterday is a complete day

    page.click('#rangeChips [data-range="today"]')
    page.wait_for_function(f"document.querySelector('#fFrom').value === '{today}'")
    assert page.input_value("#fTo") == today.isoformat()
    page.wait_for_selector("#laNote", state="visible")             # today is still filling up in LA
    assert "giờ Thái Bình Dương" in page.inner_text("#laNote")

    page.click('#rangeChips [data-days="30"]')
    page.wait_for_selector('#rangeChips [data-days="30"].on')
    assert "Khoảng dài" not in page.inner_text("#scanRange")
    page.click('#rangeChips [data-days="90"]')
    page.wait_for_selector('#rangeChips [data-days="90"].on')
    assert page.input_value("#fFrom") == (today - timedelta(days=90)).isoformat()
    assert "Khoảng dài" in page.inner_text("#scanRange")          # > 30 days: big pages may take > 10 min


def test_window_counts_new_ads_that_reuse_old_creatives(site):
    base, ad, app, _ = site
    today = ad_library_today()
    con = storage.connect(app.db)
    old = storage.load_ad(con, ad.ad_archive_id)
    old.start_day = (today - timedelta(days=40)).isoformat()
    old.collation_id = "C1"
    again = storage.load_ad(con, ad.ad_archive_id)
    again.ad_archive_id, again.collation_id = "888000888", "C1"     # same creative, run again yesterday
    again.start_day = (today - timedelta(days=1)).isoformat()
    storage.upsert_ads(con, [old, again])
    y = again.start_day
    lib = json.loads(get(base + f"/api/library?since={y}&until={y}")[2])
    assert lib["cards"] == [] and (lib["new_ads"], lib["reused_ads"]) == (1, 1)
