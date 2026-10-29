"""Pure parsers for Meta Ad Library payloads (no network, no browser).

Ad Library ships ads in two places: JSON <script> blobs in the first HTML
response (first ~30 ads) and `AdLibrarySearchPaginationQuery` GraphQL
responses on scroll (10 ads each). Both carry the same
`search_results_connection` shape, so one walker handles both.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Ad Library stamps start_date at 00:00 America/Los_Angeles (measured 768/768
# nodes). Converting in this zone yields the "Started running on" day the web shows.
AD_LIBRARY_TZ = ZoneInfo("America/Los_Angeles")

_SCRIPT_RE = re.compile(r'<script type="application/json"[^>]*>(.*?)</script>', re.S)


@dataclass
class Ad:
    ad_archive_id: str
    page_id: str
    page_name: str
    start_day: str          # YYYY-MM-DD, Ad Library day (LA time)
    end_day: str | None
    is_active: bool
    collation_id: str | None
    collation_count: int
    display_format: str | None
    link_url: str | None
    destination: str | None  # normalized app store id / domain
    body: str | None

    @property
    def creative_key(self) -> str:
        """Meta's own content grouping ("N ads use this creative"); fall back to the ad itself."""
        return self.collation_id or self.ad_archive_id


@dataclass
class PageInfo:
    page_id: str
    page_name: str | None = None
    owner: str | None = None          # confirmed_page_owner.name
    owner_location: str | None = None # owner's registered city, country (when public)
    verification: str | None = None
    category: str | None = None
    likes: int | None = None
    page_alias: str | None = None
    ig_username: str | None = None
    ig_followers: int | None = None
    created_day: str | None = None
    name_changes: int = 0
    admin_countries: list[str] = field(default_factory=list)
    profile_url: str | None = None


def day_of(epoch: int | None) -> str | None:
    if not epoch:
        return None
    return datetime.fromtimestamp(int(epoch), AD_LIBRARY_TZ).date().isoformat()


def unwrap_link(url: str | None) -> str | None:
    """Decode Facebook's outbound redirector `l.facebook.com/l.php?u=<real>`."""
    if not url:
        return None
    p = urllib.parse.urlparse(url)
    if p.netloc.endswith("l.facebook.com") and p.path.startswith("/l.php"):
        real = urllib.parse.parse_qs(p.query).get("u", [None])[0]
        return real or url
    return url


def destination_of(url: str | None) -> str | None:
    """Collapse a landing URL to what it promotes: store app id, else bare domain."""
    url = unwrap_link(url)
    if not url:
        return None
    if "://" not in url:
        url = "http://" + url
    p = urllib.parse.urlparse(url)
    host = p.netloc.lower().removeprefix("www.")
    if host == "play.google.com":
        app = urllib.parse.parse_qs(p.query).get("id", [None])[0]
        return f"play:{app}" if app else host
    if host in ("apps.apple.com", "itunes.apple.com"):
        m = re.search(r"/id(\d+)", p.path)
        return f"appstore:{m.group(1)}" if m else host
    return host or None


def _first_link(snapshot: dict) -> str | None:
    if snapshot.get("link_url"):
        return snapshot["link_url"]
    for card in snapshot.get("cards") or []:
        if card.get("link_url"):
            return card["link_url"]
    return None


def ad_from_node(node: dict) -> Ad | None:
    if not node.get("ad_archive_id") or not node.get("start_date"):
        return None
    snap = node.get("snapshot") or {}
    link = unwrap_link(_first_link(snap))
    body = (snap.get("body") or {}).get("text") if isinstance(snap.get("body"), dict) else snap.get("body")
    return Ad(
        ad_archive_id=str(node["ad_archive_id"]),
        page_id=str(node.get("page_id") or snap.get("page_id") or ""),
        page_name=node.get("page_name") or snap.get("page_name") or "",
        start_day=day_of(node["start_date"]),
        end_day=day_of(node.get("end_date")),
        is_active=bool(node.get("is_active")),
        collation_id=str(node["collation_id"]) if node.get("collation_id") else None,
        collation_count=int(node.get("collation_count") or 1),
        display_format=snap.get("display_format"),
        link_url=link,
        destination=destination_of(link),
        body=body,
    )


def _walk_connections(obj):
    """Yield every `search_results_connection` dict anywhere in the tree."""
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            conn = cur.get("search_results_connection")
            if isinstance(conn, dict):
                yield conn
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)


def parse_payload(obj) -> tuple[list[Ad], int | None]:
    """Return (ads, total_count_shown_by_ad_library) from one decoded JSON object."""
    ads: list[Ad] = []
    total = None
    for conn in _walk_connections(obj):
        if conn.get("count") is not None:
            total = int(conn["count"])
        for edge in conn.get("edges") or []:
            for node in (edge.get("node") or {}).get("collated_results") or []:
                ad = ad_from_node(node)
                if ad:
                    ads.append(ad)
    return ads, total


def parse_graphql_text(text: str) -> tuple[list[Ad], int | None]:
    """GraphQL responses may be several JSON documents separated by newlines."""
    ads: list[Ad] = []
    total = None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        got, t = parse_payload(obj)
        ads.extend(got)
        total = t if t is not None else total
    return ads, total


def parse_initial_html(html: str) -> tuple[list[Ad], int | None]:
    """Ads embedded in the first HTML response's JSON <script> tags."""
    ads: list[Ad] = []
    total = None
    for m in _SCRIPT_RE.finditer(html):
        blob = m.group(1)
        if "search_results_connection" not in blob:
            continue
        try:
            got, t = parse_payload(json.loads(blob))
        except json.JSONDecodeError:
            continue
        ads.extend(got)
        total = t if t is not None else total
    return ads, total


def parse_page_info(obj, page_id: str) -> PageInfo | None:
    """Page transparency block from the Ad Library "About" GraphQL response."""
    # Walk the whole response: the blocks sit under `data.ad_library_main` for
    # some pages (Nike) and directly under `data` for others (Highlands).
    stack, header, page = [obj], None, None
    while stack:  # locate blocks by shape: Meta renames wrapper keys often
        cur = stack.pop()
        if isinstance(cur, dict):
            if str(cur.get("page_id")) == page_id and "page_category" in cur:
                header = cur
            if str(cur.get("id")) == page_id and "pages_transparency_info" in cur:
                page = cur
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    if header is None and page is None:
        return None
    header, page = header or {}, page or {}
    tr = page.get("pages_transparency_info") or {}
    hist = tr.get("history_items") or []
    created = next((h.get("event_time") for h in hist if h.get("item_type") == "CREATION"), None)
    admins = (tr.get("admin_locations") or {}).get("admin_country_counts") or []
    owner = page.get("confirmed_page_owner") or {}
    addr = (owner.get("information") or {}).get("address") or {}
    return PageInfo(
        page_id=page_id,
        page_name=header.get("page_name") or page.get("name"),
        owner=owner.get("name"),
        owner_location=", ".join(v for v in (addr.get("city"), addr.get("country")) if v) or None,
        verification=header.get("page_verification"),
        category=header.get("page_category"),
        likes=header.get("likes"),
        page_alias=header.get("page_alias"),
        ig_username=header.get("ig_username"),
        ig_followers=header.get("ig_followers"),
        # real event timestamp (not a 00:00-LA stamp): UTC day matches the web's "Page created on"
        created_day=datetime.fromtimestamp(int(created), timezone.utc).date().isoformat() if created else None,
        name_changes=sum(1 for h in hist if h.get("item_type") == "NAME_CHANGE"),
        admin_countries=[f"{(a.get('country') or {}).get('iso_name')} ({a.get('count')})" for a in admins],
        profile_url=header.get("page_profile_uri"),
    )


_RESULTS_RE = re.compile(r"~?\s*([\d][\d,.]*)\s+results?\b", re.I)


def results_count_from_text(text: str) -> int | None:
    """'~7,600 results' / '~9 results' shown above the ad grid → 7600 / 9 (approximate)."""
    m = _RESULTS_RE.search(text or "")
    if not m:
        return None
    return int(re.sub(r"[,.]", "", m.group(1)))


def parse_page_info_text(text: str, page_id: str) -> PageInfo | None:
    """Multi-document GraphQL text → the last PageInfo found (block may sit on any line)."""
    found = None
    for line in text.splitlines():
        if "pages_transparency_info" not in line:
            continue
        try:
            found = parse_page_info(json.loads(line), page_id) or found
        except json.JSONDecodeError:
            continue
    return found


_PAGE_ID_RES = [
    re.compile(r'"associated_page_id":"(\d+)"'),
    re.compile(r'"delegate_page":\{[^{}]*?"id":"(\d+)"'),
]


def page_id_from_fanpage_html(html: str) -> str | None:
    """Ad Library page_id from a logged-out fanpage HTML.

    Do NOT use `userID` / `fb://profile/<id>`: on new-style Pages that is the
    profile id (Nike: 100044541544829), which Ad Library does not accept.
    """
    for rx in _PAGE_ID_RES:
        m = rx.search(html)
        if m:
            return m.group(1)
    return None


def parse_page_input(text: str) -> tuple[str | None, str | None]:
    """Return (page_id, fanpage_url). A bare number or ?id=/view_all_page_id= is used as-is."""
    text = text.strip()
    if re.fullmatch(r"\d{5,}", text):
        return text, None
    if "://" not in text and "facebook.com" not in text:
        return None, f"https://www.facebook.com/{text.strip('/')}"
    if "://" not in text:
        text = "https://" + text
    q = urllib.parse.parse_qs(urllib.parse.urlparse(text).query)
    for key in ("view_all_page_id", "id"):
        if q.get(key) and q[key][0].isdigit():
            # profile.php?id= is a profile id, still needs resolving
            if key == "id" and "profile.php" in text:
                return None, text
            return q[key][0], None
    return None, text
