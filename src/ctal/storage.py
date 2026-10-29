"""SQLite storage. Upsert by ad_archive_id so re-scans never duplicate rows."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from ctal.parse_ad_library_payload import Ad, PageInfo

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
  page_id TEXT PRIMARY KEY,
  info_json TEXT NOT NULL,
  input TEXT,
  last_scan_at TEXT,
  last_scan_json TEXT
);
CREATE TABLE IF NOT EXISTS ads (
  ad_archive_id TEXT PRIMARY KEY,
  page_id TEXT NOT NULL,
  page_name TEXT,
  start_day TEXT NOT NULL,
  end_day TEXT,
  is_active INTEGER NOT NULL,
  collation_id TEXT,
  collation_count INTEGER,
  display_format TEXT,
  link_url TEXT,
  destination TEXT,
  body TEXT,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ads_page_day ON ads(page_id, start_day);
"""

AD_COLS = ["ad_archive_id", "page_id", "page_name", "start_day", "end_day", "is_active", "collation_id",
           "collation_count", "display_format", "link_url", "destination", "body"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def upsert_ads(con: sqlite3.Connection, ads: list[Ad], seen_at: str | None = None) -> tuple[int, int]:
    """Return (inserted, updated). first_seen is written once; everything else refreshes."""
    seen_at = seen_at or now_iso()
    known = {r[0] for r in con.execute(
        f"SELECT ad_archive_id FROM ads WHERE ad_archive_id IN ({','.join('?' * len(ads))})",
        [a.ad_archive_id for a in ads])} if ads else set()
    for a in ads:
        vals = [getattr(a, c) for c in AD_COLS]
        con.execute(
            f"INSERT INTO ads ({','.join(AD_COLS)}, first_seen, last_seen) VALUES ({','.join('?' * (len(AD_COLS) + 2))}) "
            f"ON CONFLICT(ad_archive_id) DO UPDATE SET "
            + ", ".join(f"{c}=excluded.{c}" for c in AD_COLS[1:]) + ", last_seen=excluded.last_seen",
            vals + [seen_at, seen_at],
        )
    con.commit()
    inserted = len({a.ad_archive_id for a in ads} - known)
    return inserted, len({a.ad_archive_id for a in ads}) - inserted


def save_page(con: sqlite3.Connection, info: PageInfo, user_input: str | None, scan: dict | None) -> None:
    con.execute(
        "INSERT INTO pages (page_id, info_json, input, last_scan_at, last_scan_json) VALUES (?,?,?,?,?) "
        "ON CONFLICT(page_id) DO UPDATE SET info_json=excluded.info_json, input=COALESCE(excluded.input, pages.input), "
        "last_scan_at=excluded.last_scan_at, last_scan_json=excluded.last_scan_json",
        (info.page_id, json.dumps(asdict(info), ensure_ascii=False), user_input, now_iso(),
         json.dumps(scan, ensure_ascii=False) if scan else None),
    )
    con.commit()


def load_page(con: sqlite3.Connection, page_id: str) -> tuple[PageInfo, dict | None] | None:
    r = con.execute("SELECT info_json, last_scan_json FROM pages WHERE page_id=?", (page_id,)).fetchone()
    if not r:
        return None
    return PageInfo(**json.loads(r["info_json"])), (json.loads(r["last_scan_json"]) if r["last_scan_json"] else None)


def load_ads(con: sqlite3.Connection, page_id: str) -> list[Ad]:
    rows = con.execute(f"SELECT {','.join(AD_COLS)} FROM ads WHERE page_id=?", (page_id,)).fetchall()
    return [Ad(**{c: (bool(r[c]) if c == "is_active" else r[c]) for c in AD_COLS}) for r in rows]


def list_pages(con: sqlite3.Connection) -> list[str]:
    return [r[0] for r in con.execute("SELECT page_id FROM pages ORDER BY page_id")]
