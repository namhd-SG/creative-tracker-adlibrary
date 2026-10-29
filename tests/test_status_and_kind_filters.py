"""Global filters: Active/Inactive and Video/Image, decided per creative, on both tabs."""
import json
from datetime import timedelta

import pytest
from playwright.sync_api import sync_playwright

from ctal import storage
from ctal.parse_ad_library_payload import ad_library_today
from ctal.web_data import by_kind, by_status

from test_web_server_endpoints import get, post, site  # noqa: F401  (shared live-server fixture)


def seed(app, ad):
    """4 creatives today: video+running, video+stopped, image+stopped, and a mixed DCO
    (one stopped image ad + one running video ad ⇒ the creative is Active AND Video)."""
    con = storage.connect(app.db)
    day = ad_library_today().isoformat()
    base = storage.load_ad(con, ad.ad_archive_id)
    rows = []
    for aid, coll, active, kind in (("101", "V_RUN", True, "video"), ("102", "V_OFF", False, "video"),
                                    ("103", "I_OFF", False, "image"), ("104", "MIX", False, "image"),
                                    ("105", "MIX", True, "video")):
        a = storage.load_ad(con, ad.ad_archive_id)
        a.ad_archive_id, a.collation_id, a.is_active, a.kind, a.start_day = aid, coll, active, kind, day
        rows.append(a)
    base.start_day = (ad_library_today() - timedelta(days=200)).isoformat()   # keep the fixture ad out
    storage.upsert_ads(con, rows + [base])
    return {r.ad_archive_id: r for r in rows}


def test_rules_are_per_creative(site):
    base, ad, app, _ = site
    rows = list(seed(app, ad).values())
    assert {a.ad_archive_id for a in by_status(rows, "active")} == {"101", "104", "105"}   # MIX has a running ad
    assert {a.ad_archive_id for a in by_status(rows, "inactive")} == {"102", "103"}
    assert {a.ad_archive_id for a in by_kind(rows, "video")} == {"101", "102", "104", "105"}  # DCO with a video
    assert {a.ad_archive_id for a in by_kind(rows, "image")} == {"103"}


def keys(base, qs):
    return {c["key"] for c in json.loads(get(base + "/api/library?" + qs)[2])["cards"]}


def test_library_and_competitors_follow_the_filters(site):
    base, ad, app, _ = site
    seed(app, ad)
    assert keys(base, "status=all&kind=all") == {"V_RUN", "V_OFF", "I_OFF", "MIX"}
    assert keys(base, "status=active") == {"V_RUN", "MIX"}
    assert keys(base, "status=inactive&kind=image") == {"I_OFF"}
    assert keys(base, "kind=image") == {"I_OFF"}
    cards = json.loads(get(base + "/api/library?kind=video")[2])["cards"]
    assert {c["key"]: c["kind"] for c in cards}["MIX"] == "video"
    comp = lambda qs: json.loads(get(base + "/api/competitors?" + qs)[2])["apps"][0]["pages"][0]["new_creatives"]
    assert (comp("status=all"), comp("status=active"), comp("status=inactive"), comp("kind=image")) == (4, 2, 2, 1)
    assert post(base + "/api/apps", {"name": "x"})[0] == 200
    import urllib.error
    with pytest.raises(urllib.error.HTTPError) as e:
        get(base + "/api/library?status=running")
    assert e.value.code == 400


def test_filter_chips_in_the_page_are_sent_and_remembered(site):
    base, ad, app, _ = site
    seed(app, ad)
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        sent = []
        page.on("request", lambda r: sent.append(r.url) if "/api/library" in r.url else None)
        page.goto(base + "/")
        page.wait_for_selector("#feed [data-view]")
        assert page.locator("#feed [data-view]").count() == 4
        page.click('#stChips [data-st="active"]')
        page.wait_for_function("document.querySelectorAll('#feed [data-view]').length === 2")
        assert "status=active" in sent[-1] and page.get_attribute('#stChips [data-st="active"]', "class") == "chip on"
        page.click('#kindChips [data-kind="image"]')
        page.wait_for_selector("#feed .empty")                     # active + image: nothing
        assert "đang lọc" in page.inner_text("#feed .empty")
        page.click('#stChips [data-st="inactive"]')
        page.wait_for_function("document.querySelectorAll('#feed [data-view]').length === 1")
        page.reload()                                              # remembered by the browser
        page.wait_for_function("document.querySelectorAll('#feed [data-view]').length === 1")
        assert "status=inactive&kind=image" in sent[-1]
        assert page.locator('[data-f="run"], [data-f="video"], [data-f="anh"]').count() == 0   # no duplicate chips
        b.close()


def test_unknown_total_is_explained_not_flagged_as_error(site):
    base, ad, app, _ = site
    con = storage.connect(app.db)
    from ctal.parse_ad_library_payload import PageInfo
    storage.save_page(con, PageInfo(ad.page_id, "AI Hair Photo Editor"), "x",
                      {"at": "2026-10-29T09:08:00+00:00", "since": "2026-10-15", "collected": 1510,
                       "shown_total": None, "coverage": None, "warnings": []})
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.goto(base + "/")
        page.click('#tabs a[data-v="comp"]')
        page.wait_for_selector("td .st2")
        cell = page.inner_text("td:has(.st2)")
        assert "đã lướt 1510 QC" in cell and "creative mới trong khoảng xem" in cell
        assert "không biết tổng — Ad Library không báo số, không phải lỗi" in cell
        assert "lỗi:" not in cell and page.locator("td .st.err").count() == 0
        b.close()
