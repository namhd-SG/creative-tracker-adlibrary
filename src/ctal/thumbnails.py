"""Keep a local copy of each ad's preview picture.

Ad Library preview links are signed and expire ~4.5 days after the scan, so the
library would lose its pictures unless they are saved while the link is fresh.
Pictures are shrunk to 360 px (≈20 KB) with macOS `sips`; on other systems the
original (≈170 KB) is kept.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from ctal.parse_ad_library_payload import Ad

log = logging.getLogger("ctal")
THUMB_PX = 360
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"


@dataclass
class ThumbResult:
    saved: int = 0
    already: int = 0
    no_link: int = 0
    failed: int = 0


def thumb_path(thumbs_dir: Path, ad_archive_id: str) -> Path:
    return thumbs_dir / f"{ad_archive_id}.jpg"


def http_get(url: str, timeout: float = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _shrink(path: Path) -> None:
    if not shutil.which("sips"):
        return
    subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "70", "-Z", str(THUMB_PX), str(path)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def save_thumbnails(ads: list[Ad], thumbs_dir: Path, fetch=http_get, pause: float = 0.1) -> ThumbResult:
    """Download the missing previews. Never overwrites a picture already on disk."""
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    res = ThumbResult()
    for ad in ads:
        dest = thumb_path(thumbs_dir, ad.ad_archive_id)
        if dest.exists() and dest.stat().st_size > 0:
            res.already += 1
            continue
        if not ad.thumb_url:
            res.no_link += 1
            continue
        try:
            data = fetch(ad.thumb_url)
        except Exception as exc:  # expired link / network: the next scan brings a fresh link
            log.debug("thumbnail %s: %s", ad.ad_archive_id, exc)
            res.failed += 1
            continue
        tmp = dest.with_suffix(".part")
        tmp.write_bytes(data)
        _shrink(tmp)
        tmp.replace(dest)
        res.saved += 1
        time.sleep(pause)
    return res
