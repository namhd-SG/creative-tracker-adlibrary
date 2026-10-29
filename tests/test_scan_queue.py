"""Per-page scan queue: order, live states, dedupe, stop — with a fake page runner (no browser)."""
import threading
import time

from ctal import competitor_list as cl
from ctal import storage
from ctal.parse_ad_library_payload import PageInfo
from ctal.scan_jobs import ScanError, ScanQueue
from ctal.web_data import scan_plan

AL = "https://www.facebook.com/ads/library/?view_all_page_id={}"


def item(k, app="A"):
    return {"key": k, "target": AL.format(k), "app": app, "label": f"page {k}"}


class FakeRunner:
    """Runs a page when the test releases it, reporting progress like the real child process."""

    def __init__(self, fail=()):
        self.order, self.fail, self.gates = [], set(fail), {}

    def gate(self, key):
        return self.gates.setdefault(key, threading.Event())

    def __call__(self, it, on_progress):
        self.order.append(it["key"])
        on_progress({"collected": 10, "total": 40, "scrolls": 1})
        assert self.gate(it["key"]).wait(5), "test never released the page"
        if it["key"] in self.fail:
            raise ScanError("Facebook đòi đăng nhập")
        return {"page_id": it["key"], "page_name": it["label"], "collected": 40, "shown_total": 40, "coverage": 1.0}


def wait_for(cond, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    raise AssertionError("condition not reached")


def make(fail=()):
    run = FakeRunner(fail)
    return ScanQueue("db", "list", "out", run_page=run, pause=(0, 0)), run


def test_states_move_from_queued_to_running_to_done():
    q, run = make()
    assert q.enqueue([item("1"), item("2"), item("3")]) == 3
    wait_for(lambda: q.status()["pages"]["1"]["status"] == "running")
    st = q.status()
    assert st["running"] and st["current"] == "1"
    assert st["pages"]["1"]["collected"] == 10 and st["pages"]["1"]["total"] == 40   # live progress
    assert (st["pages"]["2"]["status"], st["pages"]["2"]["pos"]) == ("queued", 1)
    assert st["pages"]["3"]["pos"] == 2
    run.gate("1").set()
    wait_for(lambda: q.status()["pages"]["1"]["status"] == "done")
    assert q.status()["pages"]["1"]["coverage"] == 1.0 and q.status()["batch"]["done"] == 1   # done before the batch ends
    run.gate("2").set(), run.gate("3").set()
    wait_for(lambda: not q.status()["running"])
    assert run.order == ["1", "2", "3"] and q.status()["batch"] == {"total": 3, "done": 3, "failed": 0}


def test_waiting_or_running_pages_are_not_queued_twice():
    q, run = make()
    q.enqueue([item("1"), item("2")])
    wait_for(lambda: q.status()["current"] == "1")
    assert q.enqueue([item("1"), item("2"), item("9")]) == 1          # only the new page
    for k in ("1", "2", "9"):
        run.gate(k).set()
    wait_for(lambda: not q.status()["running"])
    assert run.order == ["1", "2", "9"]


def test_error_is_kept_per_page_and_queue_continues():
    q, run = make(fail={"1"})
    q.enqueue([item("1"), item("2")])
    run.gate("1").set(), run.gate("2").set()
    wait_for(lambda: not q.status()["running"])
    pages = q.status()["pages"]
    assert pages["1"]["status"] == "error" and "đăng nhập" in pages["1"]["message"]
    assert pages["2"]["status"] == "done" and q.status()["batch"]["failed"] == 1


def test_stop_keeps_finished_pages_and_drops_the_queue():
    q, run = make()
    q.enqueue([item("1"), item("2"), item("3")])
    run.gate("1").set()
    wait_for(lambda: q.status()["current"] == "2")
    q.stop()
    run.gate("2").set()                                               # the child is gone; runner returns
    wait_for(lambda: not q.status()["running"])
    pages = q.status()["pages"]
    assert pages["1"]["status"] == "done"
    assert "3" not in pages                                           # never started, back to its last stored state
    assert run.order == ["1", "2"]


def test_plan_orders_unscanned_then_small_pages(tmp_path):
    con = storage.connect(tmp_path / "t.db")
    entries = []
    cl.add_app(entries, "A")
    for pid in ("111111", "222222", "333333", "444444"):
        cl.add_page(entries, "A", AL.format(pid))
    cl.add_app(entries, "B")
    cl.add_page(entries, "B", "https://www.facebook.com/somebrand")   # fanpage link, id unknown yet
    for pid, shown in (("111111", 900), ("222222", 12), ("444444", None)):
        storage.save_page(con, PageInfo(pid, f"P{pid}"), AL.format(pid),
                          {"shown_total": shown, "collected": 5 if shown is None else shown})
    plan = scan_plan(con, entries)
    assert [p["key"] for p in plan] == ["333333", "https://www.facebook.com/somebrand", "444444", "222222", "111111"]
    assert [p["key"] for p in scan_plan(con, entries, app="B")] == ["https://www.facebook.com/somebrand"]
    assert [p["key"] for p in scan_plan(con, entries, key="222222")] == ["222222"]
    assert plan[-1]["label"] == "P111111" and plan[-1]["target"] == AL.format("111111")


def test_parse_range_and_days_since():
    from datetime import date
    from ctal.web_data import days_since, parse_range
    assert days_since("2026-10-15", today=date(2026, 10, 29)) == 14
    assert days_since("2026-10-29", today=date(2026, 10, 29)) == 0          # "Hôm nay": today only
    assert days_since("2026-10-28", today=date(2026, 10, 29)) == 1          # "Hôm qua"
    assert parse_range("2026-10-20", "2026-10-10", 14) == ("2026-10-10", "2026-10-20")
    import pytest
    with pytest.raises(ValueError):
        parse_range("hôm qua", None, 14)
