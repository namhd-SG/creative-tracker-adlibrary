"""Scan queue for the web app: one page at a time, live status for every page.

Each page runs as a child process `ctal scan <link> --progress` that prints
`@progress {...}` after every scroll and `@result {...}` / `@error {...}` at the
end; the queue turns those lines into a per-page state the page polls:

    queued (with its position) → running (collected/total/scrolls) → done | error | stopped

Stopping kills only the page being scanned; pages already done keep their data
(it is written to SQLite as each page finishes). Media-link refreshes for
downloads take the same lock, so two browsers never run at once.
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable

ProgressFn = Callable[[dict], None]
RunPage = Callable[[dict, ProgressFn], dict]   # (item, on_progress) -> result dict; raises on failure


class ScanError(Exception):
    pass


class ScanQueue:
    def __init__(self, db: Path, list_file: Path, out: Path, days: int = 14, cwd: Path | None = None,
                 run_page: RunPage | None = None, pause: tuple[float, float] = (8, 15)):
        self.db, self.list_file, self.out, self.days, self.cwd = db, list_file, out, days, cwd
        self.pause = pause
        self._run_page = run_page or self._run_page_subprocess
        self._cv = threading.Condition()
        self._run_lock = threading.Lock()        # one browser at a time (scan or link refresh)
        self._queue: list[dict] = []             # waiting items, in order
        self.pages: dict[str, dict] = {}         # key -> live state
        self.current: str | None = None
        self.batch = {"total": 0, "done": 0, "failed": 0}
        self._stop = False
        self._proc: subprocess.Popen | None = None
        self._worker: threading.Thread | None = None
        self._log: deque[str] = deque(maxlen=200)

    # ---------- public ----------
    def enqueue(self, items: list[dict]) -> int:
        """items = [{key, target, app, label}]. Pages already waiting or running are skipped."""
        added = 0
        with self._cv:
            if not self._queue and self.current is None:
                self.batch = {"total": 0, "done": 0, "failed": 0}
            busy = {i["key"] for i in self._queue} | ({self.current} if self.current else set())
            for it in items:
                if it["key"] in busy:
                    continue
                self._queue.append(it)
                busy.add(it["key"])
                self.pages[it["key"]] = {"status": "queued", "app": it.get("app"), "label": it.get("label"),
                                         "days": it.get("days")}
                added += 1
            self.batch["total"] += added
            self._stop = False
            if added and (self._worker is None or not self._worker.is_alive()):
                self._worker = threading.Thread(target=self._loop, daemon=True)
                self._worker.start()
            self._cv.notify_all()
        return added

    def stop(self) -> None:
        """Drop the waiting pages and kill the one being scanned; finished pages keep their data."""
        with self._cv:
            self._stop = True
            for it in self._queue:
                self.pages.pop(it["key"], None)
            self.batch["total"] -= len(self._queue)
            self._queue.clear()
            proc = self._proc
            self._cv.notify_all()
        if proc and proc.poll() is None:
            proc.terminate()
        self._log.append("⏹ Đã dừng theo yêu cầu.")

    def status(self) -> dict:
        with self._cv:
            pages = {k: dict(v) for k, v in self.pages.items()}
            for pos, it in enumerate(self._queue, 1):
                pages[it["key"]]["pos"] = pos
            cur = pages.get(self.current) if self.current else None
            return {"running": self.current is not None or bool(self._queue), "current": self.current,
                    "current_page": cur, "batch": dict(self.batch), "pages": pages, "log": list(self._log)[-60:]}

    def refresh_page(self, page_id: str) -> None:
        """Rescan one page now (fresh media links for a download). Waits for the page being scanned."""
        with self._run_lock:
            cmd = self._cmd(page_id)
            r = subprocess.run(cmd, cwd=self.cwd, capture_output=True, text=True)
            self._log.append(f"↻ làm mới link page {page_id}: rc={r.returncode}")

    # ---------- worker ----------
    def _loop(self) -> None:
        first = True
        while True:
            with self._cv:
                if self._stop or not self._queue:
                    self.current = None
                    return
                if not first:                    # be gentle between pages (stop wakes us up)
                    self._cv.wait(timeout=random.uniform(*self.pause))
                    if self._stop or not self._queue:
                        self.current = None
                        return
                item = self._queue.pop(0)
                self.current = item["key"]
                self.pages[item["key"]] = {"status": "running", "app": item.get("app"), "label": item.get("label"),
                                           "collected": 0, "total": None, "scrolls": 0, "started_at": time.time()}
            first = False
            self._log.append(f"→ {item.get('app') or ''} · {item.get('label') or item['target']}")
            try:
                with self._run_lock:
                    res = self._run_page(item, lambda p, k=item["key"]: self._on_progress(k, p))
                state = {"status": "done", "at": time.time(), **{k: res.get(k) for k in
                         ("page_id", "page_name", "collected", "shown_total", "coverage", "seconds", "warnings", "since")}}
                self._log.append(f"  ✓ thu {res.get('collected')}/{res.get('shown_total')} quảng cáo")
            except Exception as exc:
                stopped = self._stop
                state = {"status": "stopped" if stopped else "error", "at": time.time(), "message": str(exc)[:160]}
                self._log.append(f"  {'⏹ đã dừng' if stopped else '⚠ lỗi: ' + str(exc)[:160]}")
            with self._cv:
                self.pages[item["key"]] = {"app": item.get("app"), "label": item.get("label"), **state}
                self.batch["done"] += 1
                self.batch["failed"] += state["status"] != "done"
                self.current = None

    def _on_progress(self, key: str, p: dict) -> None:
        with self._cv:
            st = self.pages.get(key)
            if st and st.get("status") == "running":
                st.update(collected=p.get("collected"), total=p.get("total"), scrolls=p.get("scrolls"))

    # ---------- real runner ----------
    def _cmd(self, target: str, *extra: str, days: int | None = None) -> list[str]:
        return [sys.executable, "-m", "ctal.cli", "--db", str(self.db), "--list", str(self.list_file),
                "--out", str(self.out), "scan", target, "--days", str(days or self.days), "--no-report", *extra]

    def _run_page_subprocess(self, item: dict, on_progress: ProgressFn) -> dict:
        proc = subprocess.Popen(self._cmd(item["target"], "--progress", days=item.get("days")), cwd=self.cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        with self._cv:
            self._proc = proc
        result, error = None, None
        for line in proc.stdout:
            line = line.rstrip()
            if line.startswith("@progress "):
                on_progress(json.loads(line[10:]))
            elif line.startswith("@result "):
                result = json.loads(line[8:])
            elif line.startswith("@error "):
                error = json.loads(line[7:]).get("message")
            elif line:
                self._log.append(line)
        rc = proc.wait()
        with self._cv:
            self._proc = None
        if result is None:
            raise ScanError(error or (f"dừng giữa chừng (rc={rc})" if rc else "không có kết quả"))
        return result
