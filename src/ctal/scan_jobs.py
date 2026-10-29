"""Run `ctal scan` from the web page: one scan at a time, in the background, with live status.

Scans run as a child process (same Python, same --db/--list) so a browser crash
or a slow page never blocks the web server. Link refreshes for downloads use the
same lock, so they wait for a running scan instead of opening a second browser.
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path


class ScanRunner:
    def __init__(self, db: Path, list_file: Path, out: Path, days: int = 14, cwd: Path | None = None):
        self.db, self.list_file, self.out, self.days, self.cwd = db, list_file, out, days, cwd
        self._lock = threading.Lock()
        self._log: deque[str] = deque(maxlen=40)
        self.state = {"running": False, "target": None, "started_at": None, "finished_at": None, "rc": None}

    def _cmd(self, *scan_args: str) -> list[str]:
        return [sys.executable, "-m", "ctal.cli", "--db", str(self.db), "--list", str(self.list_file),
                "--out", str(self.out), "scan", "--days", str(self.days), *scan_args]

    def status(self) -> dict:
        return {**self.state, "log": list(self._log)}

    def start(self, app: str | None = None) -> bool:
        """Start a background scan of one app (or the whole list). False when a scan is already running."""
        if not self._lock.acquire(blocking=False):
            return False
        self._log.clear()
        self.state.update(running=True, target=app or "tất cả", started_at=time.time(), finished_at=None, rc=None)
        args = ["--app", app] if app else []
        threading.Thread(target=self._run, args=(self._cmd(*args),), daemon=True).start()
        return True

    def _run(self, cmd: list[str]) -> None:
        rc = -1
        try:
            proc = subprocess.Popen(cmd, cwd=self.cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1)
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    self._log.append(line)
            rc = proc.wait()
        except Exception as exc:
            self._log.append(f"LỖI: {exc}")
        finally:
            self.state.update(running=False, finished_at=time.time(), rc=rc)
            self._lock.release()

    def refresh_page(self, page_id: str) -> None:
        """Rescan one page synchronously (fresh media links). Waits for a running scan first."""
        with self._lock:
            self.state.update(running=True, target=f"làm mới link page {page_id}", started_at=time.time(),
                              finished_at=None, rc=None)
            try:
                r = subprocess.run(self._cmd(page_id, "--no-report"), cwd=self.cwd, capture_output=True, text=True)
                self._log.extend(x for x in r.stdout.splitlines()[-5:] if x)
                self.state["rc"] = r.returncode
            finally:
                self.state.update(running=False, finished_at=time.time())
