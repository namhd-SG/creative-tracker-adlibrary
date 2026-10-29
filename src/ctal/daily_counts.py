"""Daily counts: new ads / new creatives / new sets ("bộ") per Ad Library day.

All three definitions live here and only here. To make "bộ" mean Meta's
collation group instead, change `set_key` — nothing else.

- new ads (quảng cáo mới) on D: ads whose start day == D.
- new creatives (creative mới) on D: creative groups (Meta's "N ads use this
  creative" = collation_id, else the ad itself) whose EARLIEST start day == D.
  Adding more ads to an old group later never counts it again.
- new sets (bộ mới) on D: creatives first launched on D, clustered by the
  destination they promote (store app id / domain). One launch of creatives
  for one app/landing on one day = one set.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Protocol


class AdLike(Protocol):
    ad_archive_id: str
    start_day: str
    creative_key: str
    destination: str | None


@dataclass
class Creative:
    key: str
    first_day: str
    ad_ids: list[str]
    destination: str | None   # destination of the earliest ad in the group


def creatives_of(ads: Iterable[AdLike]) -> list[Creative]:
    groups: dict[str, list[AdLike]] = defaultdict(list)
    for ad in ads:
        groups[ad.creative_key].append(ad)
    out = []
    for key, members in groups.items():
        first = min(members, key=lambda a: (a.start_day, a.ad_archive_id))
        out.append(Creative(key, first.start_day, sorted(a.ad_archive_id for a in members), first.destination))
    return out


def set_key(c: Creative) -> tuple[str, str]:
    """What makes two new creatives the same "bộ". Swap this to redefine sets."""
    return (c.first_day, c.destination or "(không rõ đích)")


@dataclass
class DayRow:
    day: str
    new_ads: int
    new_creatives: int
    new_sets: int


def daily_rows(ads: Iterable[AdLike], since: str, until: str) -> list[DayRow]:
    """One row per day in [since, until], zero-filled so empty days are visible."""
    ads = list(ads)
    new_ads: dict[str, int] = defaultdict(int)
    for ad in ads:
        new_ads[ad.start_day] += 1
    creatives = creatives_of(ads)
    new_creatives: dict[str, int] = defaultdict(int)
    sets: dict[str, set] = defaultdict(set)
    for c in creatives:
        new_creatives[c.first_day] += 1
        sets[c.first_day].add(set_key(c))
    rows = []
    d, end = date.fromisoformat(since), date.fromisoformat(until)
    while d <= end:
        k = d.isoformat()
        rows.append(DayRow(k, new_ads[k], new_creatives[k], len(sets[k])))
        d += timedelta(days=1)
    return rows


def sets_detail(ads: Iterable[AdLike], since: str, until: str) -> list[dict]:
    """Each new set with its creatives, so every number can be traced back to ads."""
    out: dict[tuple, dict] = {}
    for c in creatives_of(ads):
        if not (since <= c.first_day <= until):
            continue
        k = set_key(c)
        row = out.setdefault(k, {"day": c.first_day, "destination": k[1], "creatives": 0, "ads": 0, "ad_ids": []})
        row["creatives"] += 1
        row["ads"] += len(c.ad_ids)
        row["ad_ids"].extend(c.ad_ids)
    return sorted(out.values(), key=lambda r: (r["day"], r["destination"]), reverse=True)
