"""Local web app (`ctal web`): standard library only, bound to 127.0.0.1.

GET  /                       the page (src/ctal/web/index.html)
GET  /api/library            creative cards        GET /api/competitors   apps → pages
GET  /api/scan               live status (per page) POST /api/scan {app?|key?}  queue pages
POST /api/scan/stop          drop the queue, stop the page being scanned
POST /api/apps {name,link_store}                   POST /api/pages {app,link,note}
GET  /api/media/<ad_id>      302 to a fresh video/image link (for the player)
GET  /api/download/<ad_id>   the file as an attachment
POST /api/zip {ids:[...]}    the selected creatives as one .zip
"""
from __future__ import annotations

import json
import mimetypes
import re
import tempfile
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ctal import competitor_list as cl
from ctal import storage, web_data
from ctal.media_download import MediaError, fetch_media, fresh_link, write_zip
from ctal.scan_jobs import ScanQueue

HOST = "127.0.0.1"
STATIC = Path(__file__).parent / "web"


class App:
    """Everything a request handler needs; one SQLite connection per request (thread-safe)."""

    def __init__(self, db: Path, list_file: Path, out: Path, days: int = 14):
        self.db, self.list_file, self.days = Path(db), Path(list_file), days
        self.thumbs = Path(db).parent / "thumbs"
        self.scans = ScanQueue(self.db, self.list_file, Path(out), days, cwd=Path.cwd())
        cl.ensure_file(self.list_file)
        storage.connect(self.db).close()   # create / upgrade the database once, before parallel requests

    def con(self):
        return storage.connect(self.db)

    def entries(self):
        return cl.load(self.list_file)

    def file_name(self, con, ad) -> str:
        app = web_data._page_ids(con, self.entries()).get(ad.page_id, "app")
        return web_data.download_name(app, ad, ad.start_day)


class Handler(BaseHTTPRequestHandler):
    app: App
    server_version = "ctal"

    def log_message(self, fmt, *args):  # quiet console; errors still surface as HTTP codes
        pass

    # ---------- helpers ----------
    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _file(self, path: Path) -> None:
        if not path.is_file():
            return self._json({"error": "không có file"}, 404)
        self._send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")

    @staticmethod
    def _attach(name: str) -> dict:
        return {"Content-Disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(name)}"}

    # ---------- GET ----------
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        path, q = url.path, urllib.parse.parse_qs(url.query)
        a = self.app
        try:
            if path in ("/", "/index.html"):
                return self._file(STATIC / "index.html")
            if m := re.fullmatch(r"/static/([\w.-]+)", path):
                return self._file(STATIC / m.group(1))
            if m := re.fullmatch(r"/thumbs/(\d+)\.jpg", path):
                return self._file(a.thumbs / f"{m.group(1)}.jpg")
            if path in ("/api/library", "/api/competitors"):
                since, until = web_data.parse_range(q.get("since", [None])[0], q.get("until", [None])[0], a.days)
                if path == "/api/library":
                    return self._json(web_data.library(a.con(), a.entries(), a.thumbs, since, until))
                return self._json(web_data.competitors(a.con(), a.entries(), since, until))
            if path == "/api/scan":
                return self._json(a.scans.status())
            if m := re.fullmatch(r"/api/media/(\d+)", path):
                _, url = fresh_link(a.con(), m.group(1), a.scans.refresh_page)
                self.send_response(302)
                self.send_header("Location", url)
                self.send_header("Cache-Control", "no-store")
                return self.end_headers()
            if m := re.fullmatch(r"/api/download/(\d+)", path):
                con = a.con()
                ad, data = fetch_media(con, m.group(1), a.scans.refresh_page)
                name = a.file_name(con, ad)
                return self._send(200, data, mimetypes.guess_type(name)[0] or "application/octet-stream",
                                  self._attach(name))
            return self._json({"error": "không có đường dẫn này"}, 404)
        except MediaError as exc:
            return self._json({"error": str(exc)}, 410)
        except ValueError as exc:
            return self._json({"error": str(exc)}, 400)
        except (BrokenPipeError, ConnectionResetError):
            return None

    # ---------- POST ----------
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        a = self.app
        try:
            body = self._body()
            if path == "/api/apps":
                entries = a.entries()
                status = cl.add_app(entries, body.get("name", ""), body.get("link_store", "").strip())
                cl.save(entries, a.list_file)
                return self._json({"status": status})
            if path == "/api/pages":
                entries = a.entries()
                status = cl.add_page(entries, body.get("app", ""), body.get("link", ""), body.get("note", "").strip())
                cl.save(entries, a.list_file)
                return self._json({"status": status, "page_id": cl.parse_page_input(body.get("link", ""))[0]})
            if path == "/api/scan":
                since, _ = web_data.parse_range(body.get("since"), None, a.days)
                days = web_data.days_since(since)
                plan = web_data.scan_plan(a.con(), a.entries(), body.get("app") or None, body.get("key") or None, days)
                if not plan:
                    return self._json({"error": "Không có page nào để quét."}, 400)
                added = a.scans.enqueue(plan)
                return self._json({"added": added, "planned": len(plan), "since": since, "days": days, **a.scans.status()})
            if path == "/api/scan/stop":
                a.scans.stop()
                return self._json(a.scans.status())
            if path == "/api/zip":
                con, ids = a.con(), [str(i) for i in body.get("ids", []) if str(i).isdigit()]
                items = [(i, a.file_name(con, ad)) for i in ids if (ad := storage.load_ad(con, i))]
                unknown = [i for i in ids if i not in {x[0] for x in items}]
                with tempfile.TemporaryDirectory() as tmp:
                    dest = Path(tmp) / "creative.zip"
                    ok, failed = write_zip(con, items, dest, a.scans.refresh_page)
                    failed = unknown + failed
                    if not ok:
                        return self._json({"error": "Không tải được file nào.", "failed": failed}, 410)
                    name = f"creative-tracker_{web_data.window(0)[1]}_{ok}-creative.zip"
                    return self._send(200, dest.read_bytes(), "application/zip",
                                      {**self._attach(name), "X-Failed": ",".join(failed)})
            return self._json({"error": "không có đường dẫn này"}, 404)
        except ValueError as exc:
            return self._json({"error": str(exc)}, 400)


def make_server(app: App, port: int) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"app": app})
    return ThreadingHTTPServer((HOST, port), handler)
