"""Competitor summary grouped by app: each app's pages + the app total.

The app total is computed on the UNION of the app's ads (not a sum of page
rows), so two pages launching for the same store app on the same day make
one set, exactly as within a single page.
"""
from __future__ import annotations

import csv
import html
from pathlib import Path

from ctal.parse_ad_library_payload import destination_of
from ctal.report_outputs import BASE_CSS, _local_time


def points_to_app(ads, link_store: str, since: str, until: str) -> tuple[int, int] | None:
    """(ads in the window whose link goes to this app's store id, ads in the window).

    A page can advertise several apps; a low ratio flags a shared page whose
    numbers include other apps. None when the app has no store link to compare.
    Ads routed through web funnels / tracking links count as "not pointing".
    """
    key = destination_of(link_store) if link_store else None
    if not key or ":" not in key:
        return None
    window = [a for a in ads if since <= a.start_day <= until]
    return sum(1 for a in window if a.destination == key), len(window)


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def _sums(rows) -> tuple[int, int, int]:
    return (sum(r.new_ads for r in rows), sum(r.new_creatives for r in rows), sum(r.new_sets for r in rows))


def coverage_cell(scan: dict | None) -> str:
    """Coverage as HTML: a % when the total is known, an explicit note when not, a warning on scroll cap."""
    scan = scan or {}
    cov = scan.get("coverage")
    capped = any("Chạm trần" in w for w in scan.get("warnings") or [])
    if isinstance(cov, (int, float)):
        text = f"{cov:.0%} <span class='mute small'>({scan.get('collected')}/{scan.get('shown_total')})</span>"
    else:
        text = f"không biết tổng <span class='mute small'>(thu {scan.get('collected', '?')})</span>"
    if capped or (isinstance(cov, (int, float)) and cov < 0.98):
        text += "<div class='warnc'>⚠ chưa thu hết — số có thể thiếu</div>"
    return text


def write_app_summary_csv(path: Path, blocks: list[dict]) -> None:
    """Long format: one row per (app, page or TỔNG APP, day)."""
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["app", "page_id", "page_name", "ngay", "quang_cao_moi", "creative_moi", "bo_moi"])
        for b in blocks:
            for p in b["pages"]:
                if not p["info"]:
                    continue
                for r in p["rows"]:
                    w.writerow([b["app"], p["info"].page_id, p["info"].page_name, r.day,
                                r.new_ads, r.new_creatives, r.new_sets])
            for r in b["total"]:
                w.writerow([b["app"], "", "TỔNG APP", r.day, r.new_ads, r.new_creatives, r.new_sets])


def write_app_summary_html(path: Path, blocks: list[dict], since: str, until: str) -> None:
    cards = []
    for b in blocks:
        rows = []
        for p in b["pages"]:
            info = p["info"]
            if not info:
                label = p.get("note") or p.get("page_id") or "page"
                rows.append(
                    f"<tr><td class='pg'><a href='{_e(p['input'])}' target='_blank' rel='noopener'>{_e(label)}</a>"
                    f"<div class='mute small'>{_e(p.get('page_id') or '')}</div></td>"
                    "<td colspan=7><span class='tag'>chưa quét</span></td></tr>")
                continue
            ads, cr, st = _sums(p["rows"])
            pt = p.get("points_to_app")
            pt_cell = f"{pt[0]}/{pt[1]}" if pt and pt[1] else "—"
            rows.append(
                f"<tr><td class='pg'><a href='{_e(info.page_id)}.html'>{_e(info.page_name or info.page_id)}</a>"
                f"<div class='mute small'>{_e(info.page_id)}</div></td><td class='own'>{_e(info.owner or '—')}</td>"
                f"<td>{ads}</td><td>{cr}</td><td>{st}</td><td>{pt_cell}</td>"
                f"<td>{coverage_cell(p['scan'])}</td>"
                f"<td class='mute small'>{_e(_local_time((p['scan'] or {}).get('at')) or '—')}</td></tr>")
        ads, cr, st = _sums(b["total"]) if any(p["info"] for p in b["pages"]) else ("—", "—", "—")
        rows.append(f"<tr class='total'><td>Tổng app</td><td></td><td>{ads}</td><td>{cr}</td><td>{st}</td><td></td><td></td><td></td></tr>")
        days = "".join(
            f"<tr><td>{_e(r.day)}</td><td>{r.new_ads}</td><td>{r.new_creatives}</td><td>{r.new_sets}</td></tr>"
            for r in reversed(b["total"]) if r.new_ads or r.new_creatives or r.new_sets)
        store = (f"<a href='{_e(b['link_store'])}' target='_blank' rel='noopener'>{_e(b['link_store'])}</a>"
                 if b["link_store"] else "<span class='mute'>chưa có link store</span>")
        cards.append(
            f"<div class='card'><h2>{_e(b['app'])}</h2><p class='mute small'>{store}</p>"
            "<div class='wrap'><table><thead><tr><th>Page</th><th>Chủ page</th><th>QC mới</th><th>Creative mới</th><th>Bộ mới</th>"
            f"<th title='Quảng cáo bắt đầu trong kỳ có link trỏ đúng store của app'>Trỏ đúng app</th><th>Độ phủ</th><th>Quét lúc</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
            "<details><summary>Tổng app theo ngày</summary><table><thead><tr><th>Ngày</th><th>QC mới</th>"
            f"<th>Creative mới</th><th>Bộ mới</th></tr></thead><tbody>"
            f"{days or '<tr><td colspan=4>Không có gì mới.</td></tr>'}</tbody></table></details></div>")
    page = f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Creative Tracker — Đối thủ</title>
<style>{BASE_CSS}
.mute{{color:var(--mute)}}.small{{font-size:12px}}tr.total td{{font-weight:600;border-top:2px solid var(--line)}}
details{{margin-top:12px}}summary{{cursor:pointer;color:var(--mute);font-size:13px}}
.wrap{{overflow-x:auto}}td.pg{{max-width:240px}}td.pg a{{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
td.own{{max-width:200px;overflow-wrap:anywhere}}.tag{{display:inline-block;padding:1px 8px;border-radius:10px;background:var(--line);color:var(--mute);font-size:12px}}
.warnc{{color:#b26a00;font-size:12px;margin-top:2px}}table{{table-layout:auto}}</style></head><body><main>
<h1>Đối thủ — creative mới theo app</h1>
<p class="sub">{_e(since)} → {_e(until)} · {len(blocks)} app · bấm tên page để xem chi tiết từng page</p>
{''.join(cards) or '<div class="card">Danh sách đối thủ trống.</div>'}
<p class="note">Ngày = ngày "Started running on" Ad Library hiển thị. Creative = nhóm "N quảng cáo dùng creative này" của Meta,
tính theo ngày sớm nhất. Bộ = các creative mới cùng ngày, cùng đích (app/domain). Tổng app tính trên toàn bộ quảng cáo của các page,
nên 2 page cùng tung cho 1 app trong 1 ngày chỉ là 1 bộ. "Trỏ đúng app x/y" = số quảng cáo trong kỳ có link về đúng store của app;
tỉ lệ thấp nghĩa là page quảng cáo cho nhiều app (số của page gồm cả app khác) hoặc dẫn qua trang web trung gian.</p>
</main></body></html>"""
    path.write_text(page, encoding="utf-8")
