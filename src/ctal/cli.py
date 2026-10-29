"""Command line.

    ctal app add "<tên app>" <link store>
    ctal page add "<tên app>" <link Ad Library | link fanpage | page_id>
    ctal list
    ctal scan                       # every page in doi_thu.csv
    ctal scan --app "<tên app>"     # one app
    ctal scan <link|page_id> …      # ad-hoc pages, not saved to the list
    ctal report                     # rebuild reports offline

Competitor list: ./doi_thu.csv · data: ./data/tracker.db · reports: ./out/
"""
from __future__ import annotations

import argparse
import logging
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from ctal import competitor_list as cl
from ctal import storage
from ctal.parse_ad_library_payload import ad_library_today
from ctal.thumbnails import save_thumbnails
from ctal.daily_counts import daily_rows, sets_detail
from ctal.app_summary_report import points_to_app, write_app_summary_csv, write_app_summary_html
from ctal.report_outputs import terminal_table, write_daily_csv, write_html, write_sets_csv

DB = Path("data/tracker.db")


def thumbs_dir(db: Path) -> Path:
    """Preview pictures live next to the database: data/thumbs/<ad_archive_id>.jpg."""
    return Path(db).parent / "thumbs"
OUT = Path("out")


def _window(days: int) -> tuple[str, str]:
    today = ad_library_today()   # Ad Library days are Los Angeles days
    return (today - timedelta(days=days)).isoformat(), today.isoformat()


# ---------- competitor list ----------

def _load_list(args) -> list[cl.Entry]:
    if cl.ensure_file(args.list):
        print(f"(Tạo {args.list} từ danh sách mẫu {cl.SAMPLE_FILE}.)")
    return cl.load(args.list)


def cmd_app_add(args) -> int:
    entries = _load_list(args)
    status = cl.add_app(entries, args.name, args.link_store or "")
    cl.save(entries, args.list)
    print(f'App "{args.name}": {status}. Tiếp theo: ctal page add "{args.name}" <link Ad Library của page>')
    return 0


def cmd_page_add(args) -> int:
    entries = _load_list(args)
    try:
        status = cl.add_page(entries, args.app, args.link, args.note or "")
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    cl.save(entries, args.list)
    pid = cl.parse_page_input(args.link)[0]
    print(f'Page {pid or args.link} → app "{cl.find_app(entries, args.app)}": {status}.')
    return 0


def cmd_list(args) -> int:
    entries = _load_list(args)
    if not entries:
        print(f'{args.list} trống. Thêm: ctal app add "<tên app>" <link store>')
        return 0
    con = storage.connect(args.db)
    for app, pages in cl.apps(entries).items():
        store = next((e.link_store for e in entries if e.app == app and e.link_store), "")
        print(f"■ {app}  {store}")
        if not pages:
            print("   (chưa có page)")
        for e in pages:
            pid = e.page_id or storage.page_id_for_input(con, e.link_ad_library)
            loaded = storage.load_page(con, pid) if pid else None
            name = loaded[0].page_name if loaded else "chưa quét"
            print(f"   - {pid or '?':<18} {name}   {e.ghi_chu}")
    return 0


# ---------- scan / report ----------

def _scan_targets(args) -> list[tuple[str | None, str]]:
    """(app or None, page input) pairs to scan."""
    if args.pages:
        return [(None, p) for p in args.pages]
    entries = _load_list(args)
    grouped = cl.apps(entries)
    if args.app:
        app = cl.find_app(entries, args.app)
        if not app:
            raise SystemExit(f'Không có app "{args.app}" trong {args.list}. Xem: ctal list')
        grouped = {app: grouped[app]}
    return [(app, e.link_ad_library) for app, pages in grouped.items() for e in pages]


def _machine(kind: str, **data) -> None:
    """One machine-readable line for the web app's live status: `@<kind> {json}`."""
    import json
    print(f"@{kind} " + json.dumps(data, ensure_ascii=False), flush=True)


def _progress_printer(target: str):
    return lambda collected, total, scrolls: _machine("progress", target=target, collected=collected,
                                                      total=total, scrolls=scrolls)


def cmd_scan(args) -> int:
    from ctal.ad_library_scraper import scan  # lazy: report/tests must work without a browser

    targets = _scan_targets(args)
    if not targets:
        print(f'Chưa có page nào để quét. Thêm: ctal page add "<tên app>" <link Ad Library>', file=sys.stderr)
        return 1
    con = storage.connect(args.db)
    rc = 0
    done: set[str] = set()
    attempted = 0
    for i, (app, target) in enumerate(targets):
        known = cl.parse_page_input(target)[0]
        if known and known in done:
            print(f"→ [{i + 1}/{len(targets)}] {target}: đã quét trong lượt này, bỏ qua.")
            continue
        if attempted:
            time.sleep(random.uniform(8, 15))  # be gentle between pages
        attempted += 1
        print(f"→ [{i + 1}/{len(targets)}] {app + ' · ' if app else ''}{target}", flush=True)
        try:
            res = scan(target, days=args.days, max_scrolls=args.max_scrolls, headless=not args.show,
                       progress=_progress_printer(target) if args.progress else None)
        except Exception as exc:
            print(f"  LỖI: {exc}", file=sys.stderr)
            if args.progress:
                _machine("error", target=target, message=str(exc)[:200])
            rc = 1
            continue
        done.add(res.page_id)
        ins, upd = storage.upsert_ads(con, res.ads)
        th = save_thumbnails(res.ads, thumbs_dir(args.db))
        meta = {"at": storage.now_iso(), "since": res.since, "collected": len(res.ads),
                "shown_total": res.shown_total, "coverage": res.coverage, "scrolls": res.scrolls,
                "seconds": round(res.seconds), "warnings": res.warnings}
        storage.save_page(con, res.info, target, meta)
        cov = f"{res.coverage:.0%}" if res.coverage is not None else "?"
        print(f"  page_id {res.page_id} · {res.info.page_name} · chủ page: {res.info.owner or 'không rõ'}")
        print(f"  thu {len(res.ads)}/{res.shown_total} quảng cáo (độ phủ {cov}) · mới {ins}, cập nhật {upd} · "
              f"{res.scrolls} lần cuộn · {res.seconds:.0f}s")
        print(f"  ảnh xem trước: lưu mới {th.saved}, đã có {th.already}"
              + (f", lỗi {th.failed}" if th.failed else "") + (f", không có link {th.no_link}" if th.no_link else ""))
        for w in res.warnings:
            print(f"  ⚠ {w}")
        if args.progress:
            _machine("result", target=target, page_id=res.page_id, page_name=res.info.page_name,
                     collected=len(res.ads), shown_total=res.shown_total, coverage=res.coverage,
                     seconds=round(res.seconds), warnings=res.warnings, since=res.since)
        if not args.no_report and args.pages:
            _report_one(con, res.page_id, args.days, args.out)
    if not args.no_report and not args.pages:
        _report_apps(args, con)
    return rc


def _report_one(con, page_id: str, days: int, out: Path, quiet: bool = False) -> bool:
    loaded = storage.load_page(con, page_id)
    if not loaded:
        print(f"Chưa có dữ liệu cho page {page_id} — chạy `ctal scan` trước.", file=sys.stderr)
        return False
    info, scan_meta = loaded
    ads = storage.load_ads(con, page_id)
    since, until = _window(days)
    rows = daily_rows(ads, since, until)
    sets = sets_detail(ads, since, until)
    out.mkdir(parents=True, exist_ok=True)
    daily_csv, sets_csv, page_html = out / f"{page_id}-daily.csv", out / f"{page_id}-bo.csv", out / f"{page_id}.html"
    write_daily_csv(daily_csv, page_id, rows)
    write_sets_csv(sets_csv, page_id, sets)
    write_html(page_html, info, rows, sets, scan_meta)
    if not quiet:
        print(terminal_table(info, rows))
        print(f"  CSV: {daily_csv}  ·  {sets_csv}\n  HTML: {page_html.resolve()}")
    return True


def _report_apps(args, con) -> None:
    """Per-app summary: each app's pages + an app total computed on the union of its ads."""
    entries = _load_list(args)
    since, until = _window(args.days)
    blocks = []
    for app, pages in cl.apps(entries).items():
        store = next((e.link_store for e in entries if e.app == app and e.link_store), "")
        page_blocks, all_ads, seen = [], [], set()
        for e in pages:
            pid = e.page_id or storage.page_id_for_input(con, e.link_ad_library)
            loaded = storage.load_page(con, pid) if pid else None
            if not loaded or pid in seen:
                if pid not in seen:  # same page listed twice in one app: show it once
                    page_blocks.append({"input": e.link_ad_library, "page_id": pid, "note": e.ghi_chu,
                                        "info": None, "rows": [], "scan": None})
                continue
            seen.add(pid)
            _report_one(con, pid, args.days, args.out, quiet=True)
            ads = storage.load_ads(con, pid)
            all_ads += ads
            page_blocks.append({"input": e.link_ad_library, "info": loaded[0], "scan": loaded[1],
                                "rows": daily_rows(ads, since, until),
                                "points_to_app": points_to_app(ads, store, since, until)})
        blocks.append({"app": app, "link_store": store, "pages": page_blocks,
                       "total": daily_rows(all_ads, since, until)})
    args.out.mkdir(parents=True, exist_ok=True)
    csv_path, html_path = args.out / "tong-hop-theo-app.csv", args.out / "tong-hop.html"
    write_app_summary_csv(csv_path, blocks)
    write_app_summary_html(html_path, blocks, since, until)
    print(f"\n{'App':<32}{'Page':>6}{'QC mới':>9}{'Creative mới':>14}{'Bộ mới':>8}   ({since} → {until})")
    for b in blocks:
        t = b["total"]
        print(f"{b['app'][:31]:<32}{sum(1 for p in b['pages'] if p['info']):>6}{sum(r.new_ads for r in t):>9}"
              f"{sum(r.new_creatives for r in t):>14}{sum(r.new_sets for r in t):>8}")
    print(f"\n  Tổng hợp: {html_path.resolve()}\n  CSV: {csv_path}")


def cmd_report(args) -> int:
    con = storage.connect(args.db)
    if args.pages:
        return 0 if all([_report_one(con, p, args.days, args.out) for p in args.pages]) else 1
    _report_apps(args, con)
    return 0


def cmd_web(args) -> int:
    import webbrowser
    from ctal.web_server import App, make_server

    try:
        server = make_server(App(args.db, args.list, args.out, args.days), args.port)
    except OSError as exc:
        print(f"Cổng {args.port} đang bận ({exc.strerror}). Có thể `ctal web` đang chạy ở cửa sổ khác — "
              f"mở http://127.0.0.1:{args.port} hoặc chạy lại với --port <số khác>.", file=sys.stderr)
        return 1
    url = f"http://127.0.0.1:{args.port}"
    print(f"Creative Tracker đang chạy: {url}   (Ctrl+C để tắt)")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã tắt.")
    finally:
        server.server_close()
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ctal", description="Creative Tracker từ Meta Ad Library (bản cơ bản).")
    p.add_argument("--db", type=Path, default=DB)
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--list", type=Path, default=cl.DEFAULT_FILE, help="file danh sách đối thủ (mặc định doi_thu.csv)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("app", help="Quản lý app đối thủ").add_subparsers(dest="sub", required=True)
    aa = a.add_parser("add", help='Thêm app: ctal app add "<tên>" <link store>')
    aa.add_argument("name")
    aa.add_argument("link_store", nargs="?")
    aa.set_defaults(func=cmd_app_add)

    pg = sub.add_parser("page", help="Quản lý page của app").add_subparsers(dest="sub", required=True)
    pa = pg.add_parser("add", help='Thêm page: ctal page add "<tên app>" <link Ad Library|fanpage|page_id>')
    pa.add_argument("app")
    pa.add_argument("link")
    pa.add_argument("--note", help="ghi chú tuỳ ý")
    pa.set_defaults(func=cmd_page_add)

    sub.add_parser("list", help="Xem danh sách đối thủ").set_defaults(func=cmd_list)

    s = sub.add_parser("scan", help="Quét quảng cáo (mặc định: mọi page trong danh sách đối thủ)")
    s.add_argument("pages", nargs="*", help="(tuỳ chọn) link/page_id quét lẻ, không lưu vào danh sách")
    s.add_argument("--app", help="chỉ quét các page của app này")
    s.add_argument("--days", type=int, default=14, help="số ngày gần nhất (mặc định 14)")
    s.add_argument("--max-scrolls", type=int, default=150, help="trần số lần cuộn mỗi page (mặc định 150)")
    s.add_argument("--show", action="store_true", help="hiện cửa sổ trình duyệt")
    s.add_argument("--no-report", action="store_true", help="chỉ quét, không xuất báo cáo")
    s.add_argument("--progress", action="store_true", help=argparse.SUPPRESS)  # live status lines for `ctal web`
    s.set_defaults(func=cmd_scan)

    r = sub.add_parser("report", help="Xuất lại báo cáo từ dữ liệu đã quét (không cần mạng)")
    r.add_argument("pages", nargs="*", help="page_id; bỏ trống = báo cáo tổng hợp theo app")
    r.add_argument("--days", type=int, default=14)
    r.set_defaults(func=cmd_report)

    w = sub.add_parser("web", help="Mở giao diện web trên máy (http://127.0.0.1:8770)")
    w.add_argument("--port", type=int, default=8770)
    w.add_argument("--days", type=int, default=14, help="số ngày gần nhất hiển thị (mặc định 14)")
    w.add_argument("--no-open", action="store_true", help="không tự mở trình duyệt")
    w.set_defaults(func=cmd_web)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
