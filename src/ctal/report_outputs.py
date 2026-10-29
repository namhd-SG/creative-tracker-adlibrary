"""Report outputs: terminal table, CSV files, one static HTML page per Page."""
from __future__ import annotations

import csv
import html
from datetime import datetime
from pathlib import Path

from ctal.daily_counts import DayRow
from ctal.parse_ad_library_payload import PageInfo

BASE_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c1e21;--mute:#65676b;--line:#e4e6eb;--ads:#b8c4d6;--cr:#1877f2;--set:#0b8a5f}
@media (prefers-color-scheme:dark){:root{--bg:#18191a;--card:#242526;--ink:#e4e6eb;--mute:#b0b3b8;--line:#3a3b3c;--ads:#4a5568}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:1080px;margin:0 auto;padding:24px 16px}h1{font-size:24px;margin:0 0 4px}.sub{color:var(--mute);margin:0 0 20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-bottom:16px}
h2{font-size:16px;margin:0 0 12px}dl{display:grid;grid-template-columns:200px 1fr;gap:6px 16px;margin:0}dt{color:var(--mute)}dd{margin:0}
.owner{font-size:18px;font-weight:600}
.chart{display:flex;align-items:flex-end;gap:4px;height:220px;padding-top:8px;overflow-x:auto}
.col{flex:1 0 28px;display:flex;flex-direction:column;align-items:center;height:100%}
.stack{flex:1;width:100%;display:flex;align-items:flex-end;justify-content:center;gap:2px}.b{width:30%;min-height:1px;border-radius:3px 3px 0 0}
.ads{background:var(--ads)}.cr{background:var(--cr)}.set{background:var(--set)}.lbl{font-size:11px;color:var(--mute);margin-top:4px}
.legend{display:flex;gap:16px;font-size:13px;color:var(--mute);margin-top:10px;flex-wrap:wrap}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}th{color:var(--mute);font-weight:500;font-size:13px}
td.ids{font-size:12px}td:first-child{white-space:nowrap}a{color:var(--cr)}.warn{border-color:#e0a800}.note{color:var(--mute);font-size:13px}
@media (max-width:640px){dl{grid-template-columns:1fr}dt{margin-top:6px}}
"""

DAILY_HEADER = ["ngay", "quang_cao_moi", "creative_moi", "bo_moi"]


def terminal_table(info: PageInfo, rows: list[DayRow]) -> str:
    lines = [f"{info.page_name or '?'} (page_id {info.page_id}) — chủ page: {info.owner or 'không rõ'}",
             f"{'Ngày':<12}{'QC mới':>8}{'Creative mới':>14}{'Bộ mới':>8}"]
    for r in reversed(rows):
        lines.append(f"{r.day:<12}{r.new_ads:>8}{r.new_creatives:>14}{r.new_sets:>8}")
    lines.append(f"{'Tổng':<12}{sum(r.new_ads for r in rows):>8}{sum(r.new_creatives for r in rows):>14}"
                 f"{sum(r.new_sets for r in rows):>8}")
    return "\n".join(lines)


def write_daily_csv(path: Path, page_id: str, rows: list[DayRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # BOM so Excel on Mac reads UTF-8
        w = csv.writer(f)
        w.writerow(["page_id"] + DAILY_HEADER)
        for r in rows:
            w.writerow([page_id, r.day, r.new_ads, r.new_creatives, r.new_sets])


def write_sets_csv(path: Path, page_id: str, sets: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["page_id", "ngay", "dich", "so_creative", "so_quang_cao_toi_nay", "ad_archive_ids"])
        for s in sets:
            w.writerow([page_id, s["day"], s["destination"], s["creatives"], s["ads"], " ".join(s["ad_ids"])])


def _local_time(iso: str | None) -> str | None:
    """UTC ISO stamp → 'dd/mm/yyyy HH:MM' in the viewer's (machine) local time."""
    if not iso:
        return iso
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def _fmt_int(v) -> str:
    return f"{v:,}".replace(",", ".") if isinstance(v, int) else "—"


def write_html(path: Path, info: PageInfo, rows: list[DayRow], sets: list[dict], scan: dict | None) -> None:
    peak = max([r.new_ads for r in rows] + [1])
    bars = []
    for r in rows:
        bars.append(
            f'<div class="col" title="{_e(r.day)}: {r.new_ads} QC · {r.new_creatives} creative · {r.new_sets} bộ">'
            f'<div class="stack"><div class="b ads" style="height:{r.new_ads / peak * 100:.1f}%"></div>'
            f'<div class="b cr" style="height:{r.new_creatives / peak * 100:.1f}%"></div>'
            f'<div class="b set" style="height:{r.new_sets / peak * 100:.1f}%"></div></div>'
            f'<div class="lbl">{_e(r.day[5:])}</div></div>')
    table = "".join(
        f"<tr><td>{_e(r.day)}</td><td>{r.new_ads}</td><td>{r.new_creatives}</td><td>{r.new_sets}</td></tr>"
        for r in reversed(rows))
    set_rows = "".join(
        f"<tr><td>{_e(s['day'])}</td><td>{_e(s['destination'])}</td><td>{s['creatives']}</td><td>{s['ads']}</td>"
        f"<td class='ids'>" + " ".join(
            f"<a href='https://www.facebook.com/ads/library/?id={_e(i)}' target='_blank' rel='noopener'>{_e(i)}</a>"
            for i in s["ad_ids"][:6]) + (f" … +{len(s['ad_ids']) - 6}" if len(s["ad_ids"]) > 6 else "") + "</td></tr>"
        for s in sets)
    facts = [
        ("Chủ page (Meta xác nhận)", info.owner or "không công khai"),
        ("Địa chỉ chủ page", info.owner_location),
        ("page_id", info.page_id),
        ("Ngành", info.category), ("Xác minh", info.verification),
        ("Lượt thích page", _fmt_int(info.likes)),
        ("Instagram", f"@{info.ig_username} · {_fmt_int(info.ig_followers)} người theo dõi" if info.ig_username else None),
        ("Ngày tạo page", info.created_day), ("Số lần đổi tên", info.name_changes),
        ("Người quản lý ở", ", ".join(info.admin_countries[:8]) or None),
    ]
    facts_html = "".join(f"<dt>{_e(k)}</dt><dd>{_e(v) if v not in (None, '') else '—'}</dd>" for k, v in facts)
    warn = "".join(f"<li>{_e(w)}</li>" for w in (scan or {}).get("warnings", []))
    cov = (scan or {}).get("coverage")
    scan_line = (f"Quét lúc {_e(_local_time((scan or {}).get('at')))} · lọc 'có hiển thị từ' {_e((scan or {}).get('since'))} · "
                 f"thu {_e((scan or {}).get('collected'))}/{_e((scan or {}).get('shown_total'))} quảng cáo"
                 + (f" (độ phủ {cov:.0%})" if isinstance(cov, (int, float)) else "")) if scan else ""
    page = f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Creative Tracker — {_e(info.page_name)}</title>
<style>{BASE_CSS}</style></head><body><main>
<h1>{_e(info.page_name or info.page_id)}</h1>
<p class="sub">{scan_line}</p>
{f'<div class="card warn"><h2>Cảnh báo</h2><ul>{warn}</ul></div>' if warn else ''}
<div class="card"><h2>Page này của ai</h2><p class="owner">{_e(info.owner or 'Meta không công khai chủ page')}</p><dl>{facts_html}</dl></div>
<div class="card"><h2>Theo ngày bắt đầu chạy</h2><div class="chart">{''.join(bars)}</div>
<div class="legend"><span><i class="ads"></i>Quảng cáo mới</span><span><i class="cr"></i>Creative mới</span><span><i class="set"></i>Bộ mới</span></div></div>
<div class="card"><table><thead><tr><th>Ngày</th><th>Quảng cáo mới</th><th>Creative mới</th><th>Bộ mới</th></tr></thead><tbody>{table}</tbody></table>
<p class="note">Ngày = ngày "Started running on" Ad Library hiển thị. Creative = nhóm "N quảng cáo dùng creative này" của Meta, tính theo ngày sớm nhất của nhóm. Bộ = các creative mới cùng ngày, cùng đích (app/domain). Ngày cuối có thể chưa trọn (Ad Library tính ngày theo giờ Thái Bình Dương).</p></div>
<div class="card"><h2>Chi tiết các bộ mới</h2><table><thead><tr><th>Ngày</th><th>Đích</th><th>Creative</th><th>Quảng cáo (tính tới nay)</th><th>ID thư viện (bấm để mở)</th></tr></thead><tbody>{set_rows or '<tr><td colspan=5>Không có bộ mới trong khoảng này.</td></tr>'}</tbody></table></div>
</main></body></html>"""
    path.write_text(page, encoding="utf-8")
