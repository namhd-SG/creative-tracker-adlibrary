"""Fetch a creative's video/image on demand, refreshing expired Ad Library links.

Links carry their expiry in `oe=<hex epoch>` (measured ~104-108 h after the
scan). A link that is expired, about to expire, or answered with 403/404/410
triggers ONE rescan of the ad's page (which stores fresh links), then a retry.
"""
from __future__ import annotations

import sqlite3
import time
import urllib.error
import urllib.parse
import zipfile
from pathlib import Path
from typing import Callable

from ctal import storage
from ctal.parse_ad_library_payload import Ad
from ctal.thumbnails import http_get

EXPIRY_MARGIN_S = 600
GONE = {403, 404, 410}


class MediaError(Exception):
    """The file could not be fetched even after refreshing the link."""


def link_of(ad: Ad) -> str | None:
    if ad.kind == "video":
        return ad.video_url or ad.video_sd_url
    return ad.image_url or ad.thumb_url


def expires_at(url: str | None) -> float | None:
    oe = urllib.parse.parse_qs(urllib.parse.urlparse(url or "").query).get("oe", [None])[0]
    try:
        return int(oe, 16) if oe else None
    except ValueError:
        return None


def is_stale(url: str | None, now: float | None = None) -> bool:
    if not url:
        return True
    exp = expires_at(url)
    return exp is not None and exp < (now or time.time()) + EXPIRY_MARGIN_S


def fresh_link(con: sqlite3.Connection, ad_id: str, refresh_page: Callable[[str], None]) -> tuple[Ad, str]:
    """The ad and a usable link, rescanning its page first when the stored link is stale."""
    ad = storage.load_ad(con, ad_id)
    if not ad:
        raise MediaError(f"Không có quảng cáo {ad_id} trong dữ liệu.")
    if is_stale(link_of(ad)):
        refresh_page(ad.page_id)
        ad = storage.load_ad(con, ad_id) or ad
    url = link_of(ad)
    if not url:
        raise MediaError("Quảng cáo không có link video/ảnh (có thể đã bị gỡ khỏi Ad Library).")
    return ad, url


def fetch_media(con: sqlite3.Connection, ad_id: str, refresh_page: Callable[[str], None],
                fetch: Callable[[str], bytes] | None = None) -> tuple[Ad, bytes]:
    fetch = fetch or http_get
    ad, url = fresh_link(con, ad_id, refresh_page)
    try:
        return ad, fetch(url)
    except urllib.error.HTTPError as exc:
        if exc.code not in GONE:
            raise MediaError(f"Facebook trả lỗi {exc.code}.") from exc
    refresh_page(ad.page_id)            # link died early: one rescan, one retry
    ad = storage.load_ad(con, ad_id) or ad
    url = link_of(ad)
    try:
        return ad, fetch(url)
    except Exception as exc:
        raise MediaError("Link vẫn hết hạn sau khi quét lại — quảng cáo có thể đã bị gỡ.") from exc


def write_zip(con: sqlite3.Connection, items: list[tuple[str, str]], dest: Path,
              refresh_page: Callable[[str], None], fetch: Callable[[str], bytes] | None = None) -> tuple[int, list[str]]:
    """items = [(ad_id, file name)]. Videos are already compressed ⇒ ZIP_STORED. Returns (ok, failed ids)."""
    ok, failed, used = 0, [], set()
    refreshed: set[str] = set()

    def refresh_once(page_id: str) -> None:   # many ads of one page expire together: rescan the page once
        if page_id not in refreshed:
            refreshed.add(page_id)
            refresh_page(page_id)

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_STORED) as z:
        for ad_id, name in items:
            try:
                _, data = fetch_media(con, ad_id, refresh_once, fetch)
            except Exception:
                failed.append(ad_id)
                continue
            while name in used:                 # never two entries with the same name
                stem, dot, ext = name.rpartition(".")
                name = f"{stem}-2.{ext}" if dot else name + "-2"
            used.add(name)
            z.writestr(name, data)
            ok += 1
    return ok, failed
