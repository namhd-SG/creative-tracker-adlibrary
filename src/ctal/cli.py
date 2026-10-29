"""Command line: `ctal scan <fanpage>` then `ctal report <page_id>`.

Data lives in ./data/tracker.db, reports in ./out/.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from ctal import storage
from ctal.daily_counts import daily_rows, sets_detail
from ctal.report_outputs import terminal_table, write_daily_csv, write_html, write_sets_csv

DB = Path("data/tracker.db")
OUT = Path("out")


def cmd_scan(args) -> int:
    from ctal.ad_library_scraper import scan  # lazy: report/tests must work without a browser

    con = storage.connect(args.db)
    rc = 0
    for i, target in enumerate(args.pages):
        if i:
            import random, time
            time.sleep(random.uniform(8, 15))  # be gentle between pages
        print(f"→ Quét {target} …", flush=True)
        try:
            res = scan(target, days=args.days, max_scrolls=args.max_scrolls, headless=not args.show)
        except Exception as exc:
            print(f"  LỖI: {exc}", file=sys.stderr)
            rc = 1
            continue
        ins, upd = storage.upsert_ads(con, res.ads)
        meta = {"at": storage.now_iso(), "since": res.since, "collected": len(res.ads),
                "shown_total": res.shown_total, "coverage": res.coverage, "scrolls": res.scrolls,
                "seconds": round(res.seconds), "warnings": res.warnings}
        storage.save_page(con, res.info, target, meta)
        cov = f"{res.coverage:.0%}" if res.coverage is not None else "?"
        print(f"  page_id {res.page_id} · {res.info.page_name} · chủ page: {res.info.owner or 'không rõ'}")
        print(f"  thu {len(res.ads)}/{res.shown_total} quảng cáo (độ phủ {cov}) · mới {ins}, cập nhật {upd} · "
              f"{res.scrolls} lần cuộn · {res.seconds:.0f}s")
        for w in res.warnings:
            print(f"  ⚠ {w}")
        if not args.no_report:
            _report_one(con, res.page_id, args.days, args.out)
    return rc


def _report_one(con, page_id: str, days: int, out: Path) -> bool:
    loaded = storage.load_page(con, page_id)
    if not loaded:
        print(f"Chưa có dữ liệu cho page {page_id} — chạy `ctal scan` trước.", file=sys.stderr)
        return False
    info, scan_meta = loaded
    ads = storage.load_ads(con, page_id)
    until = date.today().isoformat()
    since = (date.today() - timedelta(days=days)).isoformat()
    rows = daily_rows(ads, since, until)
    sets = sets_detail(ads, since, until)
    out.mkdir(parents=True, exist_ok=True)
    daily_csv, sets_csv, page_html = out / f"{page_id}-daily.csv", out / f"{page_id}-bo.csv", out / f"{page_id}.html"
    write_daily_csv(daily_csv, page_id, rows)
    write_sets_csv(sets_csv, page_id, sets)
    write_html(page_html, info, rows, sets, scan_meta)
    print(terminal_table(info, rows))
    print(f"  CSV: {daily_csv}  ·  {sets_csv}\n  HTML: {page_html.resolve()}")
    return True


def cmd_report(args) -> int:
    con = storage.connect(args.db)
    pages = args.pages or storage.list_pages(con)
    if not pages:
        print("Chưa quét page nào.", file=sys.stderr)
        return 1
    ok = all([_report_one(con, p, args.days, args.out) for p in pages])
    return 0 if ok else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ctal", description="Creative Tracker từ Meta Ad Library (bản cơ bản).")
    p.add_argument("--db", type=Path, default=DB)
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="Quét quảng cáo của 1 hoặc nhiều fanpage rồi xuất báo cáo")
    s.add_argument("pages", nargs="+", help="link fanpage, tên đường dẫn (vd. nike) hoặc page_id")
    s.add_argument("--days", type=int, default=14, help="số ngày gần nhất (mặc định 14)")
    s.add_argument("--max-scrolls", type=int, default=150, help="trần số lần cuộn mỗi page (mặc định 150)")
    s.add_argument("--show", action="store_true", help="hiện cửa sổ trình duyệt")
    s.add_argument("--no-report", action="store_true", help="chỉ quét, không xuất báo cáo")
    s.set_defaults(func=cmd_scan)

    r = sub.add_parser("report", help="Xuất lại báo cáo từ dữ liệu đã quét (không cần mạng)")
    r.add_argument("pages", nargs="*", help="page_id; bỏ trống = mọi page đã quét")
    r.add_argument("--days", type=int, default=14)
    r.set_defaults(func=cmd_report)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
