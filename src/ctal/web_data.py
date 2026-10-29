"""JSON for the two web tabs, built from SQLite + doi_thu.csv with the same counting code as the CLI."""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import date, timedelta
from pathlib import Path

from ctal import competitor_list as cl
from ctal import storage
from ctal.daily_counts import creatives_of, daily_rows
from ctal.parse_ad_library_payload import Ad
from ctal.thumbnails import thumb_path


def slug(v) -> str:
    """ASCII, lower-case, dash-separated piece of a download file name."""
    v = unicodedata.normalize("NFKD", str(v or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", v.lower()).strip("-")[:40] or "x"


def window(days: int, today: date | None = None) -> tuple[str, str]:
    today = today or date.today()
    return (today - timedelta(days=days)).isoformat(), today.isoformat()


def _page_ids(con, entries: list[cl.Entry]) -> dict[str, str]:
    """page_id → app (first app that lists the page); fanpage links resolve through the last scan."""
    out: dict[str, str] = {}
    for e in entries:
        pid = e.page_id or (storage.page_id_for_input(con, e.link_ad_library) if e.link_ad_library else None)
        if pid and pid not in out:
            out[pid] = e.app
    return out


def download_name(app: str, ad: Ad, first_day: str) -> str:
    ext = ".mp4" if ad.kind == "video" else ".jpg"
    return "_".join(slug(x) for x in (app, ad.page_name, first_day, ad.ad_archive_id)) + ext


def library(con: sqlite3.Connection, entries: list[cl.Entry], thumbs_dir: Path, days: int = 14) -> dict:
    """One card per creative (Meta's "N ads use this creative" group) whose first day is in the window."""
    since, until = window(days)
    page_app = _page_ids(con, entries)
    cards = []
    for pid, app in page_app.items():
        ads = storage.load_ads(con, pid)
        by_id = {a.ad_archive_id: a for a in ads}
        for c in creatives_of(ads):
            if not (since <= c.first_day <= until):
                continue
            members = sorted((by_id[i] for i in c.ad_ids), key=lambda a: (a.start_day, a.ad_archive_id))
            rep = members[0]
            with_thumb = next((a for a in members if thumb_path(thumbs_dir, a.ad_archive_id).exists()), None)
            cards.append({
                "key": c.key, "ad_id": rep.ad_archive_id, "first_day": c.first_day, "n_ads": len(members),
                "app": app, "page_id": pid, "page_name": rep.page_name, "kind": rep.kind,
                "fmt": rep.display_format, "active": any(a.is_active for a in members),
                "text": rep.body or rep.title or "", "dest": c.destination,
                "thumb": f"/thumbs/{with_thumb.ad_archive_id}.jpg" if with_thumb else None,
                "video": f"/api/media/{rep.ad_archive_id}" if rep.kind == "video" else None,
                "file": download_name(app, rep, c.first_day),
            })
    cards.sort(key=lambda x: (x["first_day"], x["ad_id"]), reverse=True)
    return {"since": since, "today": until, "cards": cards}


def competitors(con: sqlite3.Connection, entries: list[cl.Entry], days: int = 14) -> dict:
    since, until = window(days)
    apps = []
    for app, rows in cl.apps(entries).items():
        store = next((e.link_store for e in entries if e.app == app and e.link_store), "")
        pages, app_ads, seen = [], [], set()
        for e in rows:
            pid = e.page_id or storage.page_id_for_input(con, e.link_ad_library)
            if pid in seen and pid:
                continue
            seen.add(pid)
            loaded = storage.load_page(con, pid) if pid else None
            ads = storage.load_ads(con, pid) if loaded else []
            app_ads += ads
            info = loaded[0] if loaded else None
            pages.append({
                "page_id": pid, "link": e.link_ad_library, "note": e.ghi_chu,
                "name": (info.page_name if info else None) or e.ghi_chu or pid or e.link_ad_library,
                "owner": info.owner if info else None, "category": info.category if info else None,
                "scan": loaded[1] if loaded else None,
                "new_creatives": sum(r.new_creatives for r in daily_rows(ads, since, until)) if loaded else None,
            })
        apps.append({"app": app, "store": store, "pages": pages,
                     "scanned": any(p["scan"] for p in pages),
                     "days": [[r.day, r.new_ads, r.new_creatives, r.new_sets] for r in daily_rows(app_ads, since, until)]})
    apps.sort(key=lambda a: (not a["scanned"], a["app"].lower()))
    return {"since": since, "today": until, "apps": apps}
