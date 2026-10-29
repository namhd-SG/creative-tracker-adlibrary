"""Parser tests on payloads captured from the real Ad Library (29/10/2026)."""
from pathlib import Path

import pytest

from ctal.parse_ad_library_payload import (
    day_of,
    destination_of,
    page_id_from_fanpage_html,
    parse_graphql_text,
    parse_initial_html,
    parse_page_info_text,
    parse_page_input,
    unwrap_link,
)

FX = Path(__file__).parent / "fixtures"


def test_pagination_response_yields_ads_with_page_and_day():
    ads, _ = parse_graphql_text((FX / "pagination-response-nike.txt").read_text())
    assert len(ads) == 3
    assert {a.page_id for a in ads} == {"15087023444"}
    assert all(a.page_name == "Nike" for a in ads)
    assert all(len(a.start_day) == 10 for a in ads)
    by_id = {a.ad_archive_id: a for a in ads}
    ad = by_id["1403124205132974"]
    assert ad.start_day == "2026-09-24"        # start_date 1790233200 = 00:00 LA, 24 Sep
    assert ad.display_format == "DPA"
    assert ad.destination == "nike.com"
    assert by_id["26840864322244835"].destination == "nike.com.br"


def test_initial_html_payload_and_total_count():
    ads, total = parse_initial_html((FX / "initial-html-nike.html").read_text())
    assert len(ads) == 2
    assert total == 2544     # "~2,500 results" shown for the impressions filter
    assert all(a.page_id == "15087023444" for a in ads)


def test_start_date_is_ad_library_day_in_los_angeles():
    # 00:00 LA on 23 Oct = 07:00 UTC; a UTC/VN conversion would still say 23,
    # but 23:00 LA would roll to the next day in VN — LA is the reference.
    assert day_of(1792738800) == "2026-10-23"
    assert day_of(1792738800 + 23 * 3600) == "2026-10-23"


@pytest.mark.parametrize("url,expected", [
    ("https://play.google.com/store/apps/details?id=com.supercell.clashofclans", "play:com.supercell.clashofclans"),
    ("https://itunes.apple.com/app/id529479190?mt=8", "appstore:529479190"),
    ("https://apps.apple.com/vn/app/clash-of-clans/id529479190", "appstore:529479190"),
    ("http://www.highlandscoffee.com.vn/vn/menu", "highlandscoffee.com.vn"),
    ("https://l.facebook.com/l.php?u=https%3A%2F%2Fshop.example.com%2Fa%3Fb%3D1&h=AT0", "shop.example.com"),
    ("nike.com/", "nike.com"),
    (None, None),
])
def test_destination_normalises_store_ids_domains_and_fb_redirects(url, expected):
    assert destination_of(url) == expected


def test_unwrap_link_keeps_plain_urls():
    assert unwrap_link("https://a.com/x") == "https://a.com/x"
    assert unwrap_link("https://l.facebook.com/l.php?u=https%3A%2F%2Fb.com%2F") == "https://b.com/"


def test_page_info_owner_from_about_tab():
    nike = parse_page_info_text((FX / "about-response-nike.json").read_text(), "15087023444")
    assert nike.owner == "NIKE, Inc."
    assert nike.category == "Sportswear shop"
    assert nike.created_day == "2008-05-21"
    assert nike.name_changes == 1
    assert nike.admin_countries[0] == "United States (90)"
    # Highlands keeps the block directly under `data`, not under ad_library_main
    hl = parse_page_info_text((FX / "about-response-highlands.json").read_text(), "181603421920510")
    assert hl.owner == "HIGHLAND COFFEE SERVICE JOINT STOCK COMPANY"
    assert hl.owner_location == "HỒ CHÍ MINH, Vietnam"
    assert hl.created_day == "2011-10-11"     # web shows "Page created on 11 Oct 2011"
    assert hl.page_name == "Highlands Coffee"


def test_page_info_absent_for_other_page():
    assert parse_page_info_text((FX / "about-response-nike.json").read_text(), "999") is None


def test_fanpage_html_gives_ad_library_id_not_profile_id():
    html = (FX / "fanpage-nike-snippet.html").read_text()
    assert "100044541544829" in html            # the trap: profile id is present too
    assert page_id_from_fanpage_html(html) == "15087023444"


@pytest.mark.parametrize("text,expected", [
    ("15087023444", ("15087023444", None)),
    ("nike", (None, "https://www.facebook.com/nike")),
    ("https://www.facebook.com/nike/", (None, "https://www.facebook.com/nike/")),
    ("facebook.com/highlandscoffeevietnam", (None, "https://facebook.com/highlandscoffeevietnam")),
    ("https://www.facebook.com/ads/library/?view_all_page_id=447775968580065&x=1", ("447775968580065", None)),
    ("https://www.facebook.com/profile.php?id=100064785519577",
     (None, "https://www.facebook.com/profile.php?id=100064785519577")),
])
def test_page_input_forms(text, expected):
    assert parse_page_input(text) == expected
