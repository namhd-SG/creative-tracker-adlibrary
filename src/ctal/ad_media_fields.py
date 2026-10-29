"""Media links inside an Ad Library `snapshot`: preview image, video (HD/SD), still image.

Measured 29/10/2026 on 165 real ads: every ad had a preview (`videos[]` or
`cards[]` → `video_preview_image_url`) and both `video_hd_url` / `video_sd_url`.
All of these are signed FBCDN links that expire ~104-108 h after the scan, so
thumbnails are downloaded at scan time and videos are fetched on demand.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Media:
    kind: str                    # "video" | "image"
    thumb_url: str | None        # preview picture (video poster or resized still)
    video_url: str | None        # best video: HD, else SD
    video_sd_url: str | None
    image_url: str | None        # full-size still for image ads
    title: str | None
    cta_text: str | None


def _first(items: list[dict], *keys: str) -> str | None:
    for it in items:
        for k in keys:
            if it.get(k):
                return it[k]
    return None


def media_of(snapshot: dict) -> Media:
    videos = list(snapshot.get("videos") or [])
    cards = list(snapshot.get("cards") or [])
    images = list(snapshot.get("images") or [])
    hd = _first(videos + cards, "video_hd_url")
    sd = _first(videos + cards, "video_sd_url")
    still = _first(images + cards, "original_image_url", "resized_image_url")
    thumb = (_first(videos + cards, "video_preview_image_url")
             or _first(images + cards, "resized_image_url", "original_image_url"))
    title = snapshot.get("title")
    if isinstance(title, dict):
        title = title.get("text")
    if title and "{{" in title:            # dynamic product ads keep template placeholders
        title = None
    return Media(
        kind="video" if (hd or sd) else "image",
        thumb_url=thumb, video_url=hd or sd, video_sd_url=sd, image_url=still,
        title=title, cta_text=snapshot.get("cta_text"),
    )
