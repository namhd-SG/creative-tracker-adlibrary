"""Competitor list (app → pages) and the per-app summary."""
from pathlib import Path

import pytest

from ctal import competitor_list as cl
from ctal import storage
from ctal.app_summary_report import write_app_summary_csv, write_app_summary_html
from ctal.cli import main
from ctal.daily_counts import daily_rows
from ctal.parse_ad_library_payload import Ad, PageInfo, parse_graphql_text

FX = Path(__file__).parent / "fixtures"
REPO = Path(__file__).parent.parent
AL = "https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=ALL&view_all_page_id={}&search_type=page&media_type=all"


def test_add_app_then_pages_and_dedupe(tmp_path):
    f = tmp_path / "doi_thu.csv"
    e = []
    assert cl.add_app(e, "Clash of Clans", "https://play.google.com/store/apps/details?id=com.supercell.clashofclans") == "đã thêm"
    assert cl.add_app(e, "clash of clans") == "đã có"                       # case-insensitive
    assert cl.add_page(e, "CLASH OF CLANS", AL.format("447775968580065")) == "đã thêm"
    assert cl.add_page(e, "Clash of Clans", "447775968580065") == "đã có"   # same page_id, other form
    assert cl.add_page(e, "Clash of Clans", "https://www.facebook.com/ClashofClans") == "đã thêm"
    with pytest.raises(ValueError):
        cl.add_page(e, "App chưa có", "123456789")
    cl.save(e, f)
    back = cl.load(f)
    assert [(x.app, x.page_id) for x in back] == [("Clash of Clans", "447775968580065"), ("Clash of Clans", None)]
    assert all(x.link_store.endswith("com.supercell.clashofclans") for x in back)  # store link carried to every row
    assert list(cl.apps(back)) == ["Clash of Clans"] and len(cl.apps(back)["Clash of Clans"]) == 2


def test_cli_edits_only_the_csv(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["app", "add", "Highlands", "https://www.highlandscoffee.com.vn"]) == 0
    assert main(["page", "add", "highlands", AL.format("181603421920510"), "--note", "page chính"]) == 0
    assert main(["page", "add", "Không có", "1"]) == 1
    text = (tmp_path / "doi_thu.csv").read_text(encoding="utf-8-sig").splitlines()
    assert text[0] == "app,link_store,link_ad_library,ghi_chu"
    assert len(text) == 2 and "181603421920510" in text[1] and "page chính" in text[1]
    assert main(["list"]) == 0
    assert "181603421920510" in capsys.readouterr().out


def test_sample_list_is_small_and_has_only_the_four_columns():
    rows = cl.load(REPO / "doi_thu.mau.csv")
    assert 1 <= len(cl.apps(rows)) <= 4
    assert all(r.page_id for r in rows if r.link_ad_library)         # every sample page is a usable Ad Library link
    header = (REPO / "doi_thu.mau.csv").read_text(encoding="utf-8-sig").splitlines()[0]
    assert header == ",".join(cl.COLUMNS)


def test_first_run_copies_sample(tmp_path):
    sample = tmp_path / "mau.csv"
    sample.write_text("app,link_store,link_ad_library,ghi_chu\nA,,123456789,\n", encoding="utf-8")
    target = tmp_path / "doi_thu.csv"
    assert cl.ensure_file(target, sample) is True
    assert cl.ensure_file(target, sample) is False                   # never overwrite the user's file
    assert cl.load(target)[0].page_id == "123456789"


def _ad(aid, page, day, coll, dest):
    return Ad(aid, page, "P" + page, day, None, True, coll, 1, "VIDEO", None, dest, None)


def test_app_total_is_union_not_sum():
    # Two pages, same app, same day, same store destination ⇒ 2 creatives but ONE set for the app.
    p1 = [_ad("1", "11", "2026-10-23", "c1", "play:x")]
    p2 = [_ad("2", "22", "2026-10-23", "c2", "play:x")]
    per_page = [daily_rows(p, "2026-10-23", "2026-10-23")[0].new_sets for p in (p1, p2)]
    total = daily_rows(p1 + p2, "2026-10-23", "2026-10-23")[0]
    assert per_page == [1, 1]
    assert (total.new_ads, total.new_creatives, total.new_sets) == (2, 2, 1)


def test_app_summary_outputs(tmp_path):
    ads, _ = parse_graphql_text((FX / "clashofclans-910-ads-since-2026-10-22.json").read_text())
    rows = daily_rows(ads, "2026-10-22", "2026-10-28")
    info = PageInfo("447775968580065", "Clash of Clans", owner="Supercell Oy")
    blocks = [{"app": "Clash of Clans", "link_store": "https://play.google.com/store/apps/details?id=com.supercell.clashofclans",
               "pages": [{"input": "x", "info": info, "rows": rows, "scan": {"coverage": 0.996, "at": "2026-10-29T03:00:00+00:00"}},
                         {"input": "https://www.facebook.com/chuaquet", "info": None, "rows": [], "scan": None}],
               "total": rows}]
    write_app_summary_csv(tmp_path / "s.csv", blocks)
    lines = (tmp_path / "s.csv").read_text(encoding="utf-8-sig").splitlines()
    assert "Clash of Clans,447775968580065,Clash of Clans,2026-10-23,80,28,2" in lines
    assert "Clash of Clans,,TỔNG APP,2026-10-23,80,28,2" in lines
    write_app_summary_html(tmp_path / "s.html", blocks, "2026-10-22", "2026-10-28")
    page = (tmp_path / "s.html").read_text()
    assert "Supercell Oy" in page and "447775968580065.html" in page and "chưa quét" in page
    assert "100%" in page


def test_report_resolves_fanpage_rows_through_last_scan(tmp_path):
    con = storage.connect(tmp_path / "t.db")
    storage.save_page(con, PageInfo("181603421920510", "Highlands Coffee"), "https://www.facebook.com/highlandscoffeevietnam", None)
    assert storage.page_id_for_input(con, "https://www.facebook.com/highlandscoffeevietnam") == "181603421920510"
    assert storage.page_id_for_input(con, "https://www.facebook.com/khac") is None


def test_points_to_app_flags_shared_pages():
    from ctal.app_summary_report import points_to_app
    ads = [_ad("1", "11", "2026-10-23", "c1", "play:x"), _ad("2", "11", "2026-10-24", "c2", "play:other"),
           _ad("3", "11", "2026-10-24", "c3", "quiz.example.com"), _ad("4", "11", "2026-09-01", "c4", "play:x")]
    store = "https://play.google.com/store/apps/details?id=x"
    assert points_to_app(ads, store, "2026-10-20", "2026-10-30") == (1, 3)   # out-of-window ad ignored
    assert points_to_app(ads, "https://apps.apple.com/app/id1", "2026-10-20", "2026-10-30") == (0, 3)
    assert points_to_app(ads, "", "2026-10-20", "2026-10-30") is None
    assert points_to_app(ads, "https://example.com", "2026-10-20", "2026-10-30") is None  # no store id to compare
