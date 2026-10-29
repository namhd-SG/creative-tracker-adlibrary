"""Counting + storage tests on 910 real Clash of Clans ads (impressions since 22/10/2026)."""
from pathlib import Path

import pytest

from ctal import storage
from ctal.daily_counts import daily_rows, sets_detail
from ctal.parse_ad_library_payload import Ad, parse_graphql_text
from ctal.report_outputs import write_daily_csv, write_html

FX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def coc_ads():
    ads, total = parse_graphql_text((FX / "clashofclans-910-ads-since-2026-10-22.json").read_text())
    assert total == 911
    return ads


def by_day(rows):
    return {r.day: (r.new_ads, r.new_creatives, r.new_sets) for r in rows}


def test_known_days_match_hand_count(coc_ads):
    assert len(coc_ads) == 910
    got = by_day(daily_rows(coc_ads, "2026-10-22", "2026-10-28"))
    assert got["2026-10-23"] == (80, 28, 2)    # 80 ads, 28 creatives, 2 sets (iOS + Android)
    assert got["2026-10-27"] == (16, 14, 2)
    assert got["2026-10-24"] == (15, 4, 1)


def test_days_are_zero_filled(coc_ads):
    rows = daily_rows(coc_ads, "2026-10-29", "2026-11-02")
    assert [r.day for r in rows] == ["2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02"]
    assert all((r.new_ads, r.new_creatives, r.new_sets) == (0, 0, 0) for r in rows)


def _ad(aid, day, coll=None, dest="play:x"):
    return Ad(aid, "1", "P", day, None, True, coll, 1, "VIDEO", None, dest, None)


def test_creative_counted_once_on_earliest_day():
    ads = [_ad("a1", "2026-10-20", "C"), _ad("a2", "2026-10-25", "C"), _ad("a3", "2026-10-25", "D")]
    got = by_day(daily_rows(ads, "2026-10-20", "2026-10-25"))
    assert got["2026-10-20"] == (1, 1, 1)
    # a2 is a new ad, but joins old creative C ⇒ only D is a new creative
    assert got["2026-10-25"] == (2, 1, 1)


def test_sets_split_by_destination_and_sum_to_creatives(coc_ads):
    sets = sets_detail(coc_ads, "2026-10-23", "2026-10-23")
    assert sorted(s["destination"] for s in sets) == ["appstore:529479190", "play:com.supercell.clashofclans"]
    assert sum(s["creatives"] for s in sets) == 28
    # 80 ads started on 23/10, but those 28 creatives now hold 96 ads: 16 joined on later days.
    # Later joiners never make the set (or creative) "new" again.
    assert sum(s["ads"] for s in sets) == 96
    ids = [i for s in sets for i in s["ad_ids"]]
    assert len(ids) == len(set(ids))


def test_rescan_is_idempotent(tmp_path, coc_ads):
    con = storage.connect(tmp_path / "t.db")
    assert storage.upsert_ads(con, coc_ads, "2026-10-29T01:00:00+00:00") == (910, 0)
    first = by_day(daily_rows(storage.load_ads(con, coc_ads[0].page_id), "2026-10-15", "2026-10-29"))
    assert storage.upsert_ads(con, coc_ads, "2026-10-29T02:00:00+00:00") == (0, 910)
    assert con.execute("SELECT COUNT(*) FROM ads").fetchone()[0] == 910
    again = by_day(daily_rows(storage.load_ads(con, coc_ads[0].page_id), "2026-10-15", "2026-10-29"))
    assert first == again
    fs, ls = con.execute("SELECT MIN(first_seen), MAX(last_seen) FROM ads").fetchone()
    assert fs.startswith("2026-10-29T01") and ls.startswith("2026-10-29T02")


def test_outputs_written(tmp_path, coc_ads):
    from ctal.parse_ad_library_payload import PageInfo
    rows = daily_rows(coc_ads, "2026-10-22", "2026-10-28")
    write_daily_csv(tmp_path / "d.csv", "447775968580065", rows)
    lines = (tmp_path / "d.csv").read_text(encoding="utf-8-sig").splitlines()
    assert lines[0] == "page_id,ngay,quang_cao_moi,creative_moi,bo_moi"
    assert "447775968580065,2026-10-23,80,28,2" in lines
    write_html(tmp_path / "p.html", PageInfo("447775968580065", "Clash of Clans", owner="Supercell <Oy>"),
               rows, sets_detail(coc_ads, "2026-10-22", "2026-10-28"), None)
    page = (tmp_path / "p.html").read_text()
    assert "Supercell &lt;Oy&gt;" in page          # escaped
    assert "appstore:529479190" in page
