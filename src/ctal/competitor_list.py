"""Competitor list: one hand-editable CSV, app → its Facebook pages.

`doi_thu.csv` (one row per page; an app with 3 pages has 3 rows):

    app,link_store,link_ad_library,ghi_chu

An app row with an empty `link_ad_library` just registers the app. The CLI
`app add` / `page add` commands only append to this file; editing it in
Excel/Numbers works the same.
"""
from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass
from pathlib import Path

from ctal.parse_ad_library_payload import parse_page_input

COLUMNS = ["app", "link_store", "link_ad_library", "ghi_chu"]
DEFAULT_FILE = Path("doi_thu.csv")
SAMPLE_FILE = Path("doi_thu.mau.csv")


@dataclass
class Entry:
    app: str
    link_store: str = ""
    link_ad_library: str = ""
    ghi_chu: str = ""

    @property
    def page_id(self) -> str | None:
        """Known without network when the link carries the id (Ad Library link or bare id)."""
        if not self.link_ad_library:
            return None
        return parse_page_input(self.link_ad_library)[0]


def ensure_file(path: Path = DEFAULT_FILE, sample: Path = SAMPLE_FILE) -> bool:
    """First run: copy the sample list so the user starts from something. Returns True if copied."""
    if path.exists() or not sample.exists():
        return False
    shutil.copyfile(sample, path)
    return True


def load(path: Path = DEFAULT_FILE) -> list[Entry]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [Entry(**{c: (row.get(c) or "").strip() for c in COLUMNS})
                for row in csv.DictReader(f) if (row.get("app") or "").strip()]


def save(entries: list[Entry], path: Path = DEFAULT_FILE) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for e in entries:
            w.writerow([e.app, e.link_store, e.link_ad_library, e.ghi_chu])


def apps(entries: list[Entry]) -> dict[str, list[Entry]]:
    """App name → its page rows (insertion order kept, app-only rows dropped)."""
    out: dict[str, list[Entry]] = {}
    for e in entries:
        out.setdefault(e.app, [])
        if e.link_ad_library:
            out[e.app].append(e)
    return out


def find_app(entries: list[Entry], name: str) -> str | None:
    """Case-insensitive app lookup so `ctal page add "hailuo ai" …` finds "Hailuo AI"."""
    for e in entries:
        if e.app.lower() == name.strip().lower():
            return e.app
    return None


def add_app(entries: list[Entry], name: str, link_store: str = "") -> str:
    name = name.strip()
    if not name:
        raise ValueError("Tên app trống.")
    if find_app(entries, name):
        for e in entries:
            if e.app.lower() == name.lower() and link_store and not e.link_store:
                e.link_store = link_store
        return "đã có"
    entries.append(Entry(name, link_store))
    return "đã thêm"


def add_page(entries: list[Entry], app_name: str, link: str, note: str = "") -> str:
    app = find_app(entries, app_name)
    if not app:
        raise ValueError(f'Chưa có app "{app_name}". Thêm trước: ctal app add "{app_name}" <link store>')
    link = link.strip()
    new = Entry(app, "", link, note)
    for e in entries:
        same_id = new.page_id and e.page_id == new.page_id
        if e.app == app and (e.link_ad_library == link or same_id):
            return "đã có"
    store = next((e.link_store for e in entries if e.app == app and e.link_store), "")
    new.link_store = store
    # replace the app's placeholder row (no page yet) instead of adding a second row
    for i, e in enumerate(entries):
        if e.app == app and not e.link_ad_library:
            new.ghi_chu = note or e.ghi_chu
            entries[i] = new
            return "đã thêm"
    last = max(i for i, e in enumerate(entries) if e.app == app)
    entries.insert(last + 1, new)
    return "đã thêm"
