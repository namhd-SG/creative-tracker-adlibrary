"""Playwright collector for the public web Ad Library (no login, no API token).

Polite by design: one browser, one page at a time, random 2-3.5 s pause per
scroll, hard scroll cap, stops when Ad Library has nothing more to give.
"""
from __future__ import annotations


import logging
import random
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import date, timedelta

from playwright.sync_api import Page, sync_playwright

from ctal.parse_ad_library_payload import (
    Ad,
    PageInfo,
    page_id_from_fanpage_html,
    parse_graphql_text,
    parse_initial_html,
    parse_page_info_text,
    parse_page_input,
    results_count_from_text,
)

log = logging.getLogger("ctal")

AD_LIBRARY = "https://www.facebook.com/ads/library/"
ADS_QUERY = "AdLibrarySearchPaginationQuery"
STALE_ROUNDS = 4      # consecutive scrolls with no new ad before stopping
RETRY_BELOW = 0.95    # coverage under this ⇒ reload the page once and merge
CONTEXT_OPTS = dict(locale="en-US", timezone_id="Asia/Ho_Chi_Minh", viewport={"width": 1400, "height": 900})


@dataclass
class ScanResult:
    page_id: str
    info: PageInfo
    ads: list[Ad]
    shown_total: int | None          # "~N results" Ad Library reports for the filter
    since: str                       # impressions-since filter used
    scrolls: int
    seconds: float
    warnings: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> float | None:
        if not self.shown_total:
            return None
        return min(1.0, len(self.ads) / self.shown_total)


def ad_library_url(page_id: str, since: str) -> str:
    # `start_date[min]` filters by "had impressions on/after", NOT by start day.
    # Any ad that started on/after `since` also had impressions then, so this is
    # a safe superset; exact start days are read per ad afterwards.
    params = {
        "active_status": "all", "ad_type": "all", "country": "ALL", "media_type": "all",
        "search_type": "page", "view_all_page_id": page_id,
        "start_date[min]": since, "start_date[max]": "",
    }
    return AD_LIBRARY + "?" + urllib.parse.urlencode(params)


def _pause(lo: float = 2.0, hi: float = 3.5) -> None:
    time.sleep(random.uniform(lo, hi))


def resolve_page_id(page: Page, user_input: str) -> str:
    page_id, fanpage_url = parse_page_input(user_input)
    if page_id:
        return page_id
    page.goto(fanpage_url, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(2500)
    page_id = page_id_from_fanpage_html(page.content())
    if not page_id:
        raise RuntimeError(
            f"Không đọc được page_id từ {fanpage_url}. Có thể link sai, page bị giới hạn độ tuổi/quốc gia, "
            "hoặc Facebook đòi đăng nhập. Thử dán thẳng page_id (số) — xem README mục 'Tìm page_id thủ công'.")
    return page_id


def _collect_ads(page: Page, page_id: str, since: str, max_scrolls: int) -> tuple[dict[str, Ad], int | None, int, list[str]]:
    ads: dict[str, Ad] = {}
    total: list[int | None] = [None]
    warnings: list[str] = []

    def on_response(resp) -> None:
        if "/api/graphql" not in resp.url or resp.request.headers.get("x-fb-friendly-name") != ADS_QUERY:
            return
        try:
            got, t = parse_graphql_text(resp.text())
        except Exception as exc:  # body may be gone if the page navigated
            log.debug("skip response: %s", exc)
            return
        for a in got:
            ads[a.ad_archive_id] = a
        if t is not None:
            total[0] = t

    page.on("response", on_response)
    page.goto(ad_library_url(page_id, since), wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(4000)
    try:  # slow renders: measured once "None" total + no About on a page that shows "~110 results"
        page.wait_for_function("() => /\\d\\s+results?\\b|No ads|log in/i.test(document.body.innerText)",
                               timeout=12_000)
    except Exception:
        log.debug("results line not visible after 16s")
    got, t = parse_initial_html(page.content())
    for a in got:
        ads[a.ad_archive_id] = a
    total[0] = t if t is not None else total[0]
    body = page.locator("body").inner_text()
    if total[0] is None:
        # Big pages sometimes ship no `count` in the JSON; the visible "~7,600 results" still has it.
        total[0] = results_count_from_text(body)
    if "log in to continue" in body.lower() or "you must log in" in body.lower():
        warnings.append("Facebook đòi đăng nhập — dừng, không vượt rào.")
        page.remove_listener("response", on_response)
        return ads, total[0], 0, warnings

    scrolls, stale = 0, 0
    while scrolls < max_scrolls and stale < STALE_ROUNDS:
        if total[0] is not None and len(ads) >= total[0]:
            break
        before = len(ads)
        if stale:
            # Measured: a scroll sometimes fails to trigger the next batch (30/1135 once,
            # 1130/1135 on retry). Nudge up then down and wait longer before giving up.
            page.mouse.wheel(0, -1200)
            page.wait_for_timeout(800)
        page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        scrolls += 1
        _pause(2.0 + 3 * stale, 3.5 + 3 * stale)
        stale = stale + 1 if len(ads) == before else 0
    page.remove_listener("response", on_response)
    if scrolls >= max_scrolls:
        warnings.append(f"Chạm trần {max_scrolls} lần cuộn — số liệu có thể thiếu (xem độ phủ).")
    other = {a.page_id for a in ads.values()} - {page_id}
    if other:
        warnings.append(f"Có quảng cáo của page khác lẫn vào: {sorted(other)} — đã bỏ.")
    return {k: a for k, a in ads.items() if a.page_id == page_id}, total[0], scrolls, warnings


def _collect_page_info(page: Page, page_id: str) -> PageInfo | None:
    """Open the "About" tab of the Ad Library page header; parse the GraphQL it fires."""
    found: list[PageInfo] = []

    def on_response(resp) -> None:
        if "/api/graphql" not in resp.url:
            return
        try:
            text = resp.text()
        except Exception:
            return
        info = parse_page_info_text(text, page_id)
        if info:
            found.append(info)

    page.on("response", on_response)
    try:
        for attempt in range(2):  # one retry: the tab sometimes renders late or the click lands early
            try:
                page.evaluate("window.scrollTo(0, 0)")
                page.get_by_text("About", exact=True).first.click(timeout=10_000)
                page.wait_for_timeout(3500 + 2500 * attempt)
            except Exception as exc:
                log.warning("không mở được tab About (lần %d): %s", attempt + 1, exc)
            if found:
                break
    finally:
        page.remove_listener("response", on_response)
    return found[-1] if found else None


def scan(user_input: str, days: int = 14, max_scrolls: int = 150, headless: bool = True) -> ScanResult:
    since = (date.today() - timedelta(days=days)).isoformat()
    t0 = time.time()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        ctx = browser.new_context(**CONTEXT_OPTS)
        page = ctx.new_page()
        try:
            page_id = resolve_page_id(page, user_input)
            log.info("page_id = %s", page_id)
            _pause()
            ads, shown, scrolls, warnings = _collect_ads(page, page_id, since, max_scrolls)
            log.info("thu được %d quảng cáo / Ad Library báo %s", len(ads), shown)
            if shown and len(ads) < RETRY_BELOW * shown and scrolls < max_scrolls:
                log.warning("độ phủ %d/%d thấp — nghỉ rồi tải lại trang 1 lần", len(ads), shown)
                _pause(25, 40)
                more, shown2, scrolls2, warnings2 = _collect_ads(page, page_id, since, max_scrolls)
                ads.update(more)
                shown, scrolls = shown2 or shown, scrolls + scrolls2
                warnings += [w for w in warnings2 if w not in warnings]
            info = _collect_page_info(page, page_id)
        finally:
            ctx.close()
            browser.close()
    if info is None:
        warnings.append("Không đọc được tab About (Page của ai) — chỉ có tên page từ quảng cáo.")
        name = next((a.page_name for a in ads.values() if a.page_name), None)
        info = PageInfo(page_id=page_id, page_name=name)
    result = ScanResult(page_id, info, list(ads.values()), shown, since, scrolls, time.time() - t0, warnings)
    if result.coverage is not None and result.coverage < 0.98:
        result.warnings.append(
            f"Độ phủ {result.coverage:.0%} ({len(result.ads)}/{shown}) — số ngày có thể thiếu.")
    return result
