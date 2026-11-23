"""背景與排程掃描：酬載、儲存、多模式、失敗隔離、背景執行器（不抓網路、不連資料庫）。"""
import time

import pandas as pd
import pytest

from twscanner.core.config import load_config
from twscanner.services import jobs
from twscanner.services.jobs import JobRunner, build_payload, payload_to_result, run_scan_job


def _result(n_go=2, n_watch=1, n_rest=5, extra=None):
    sig = ["進場"] * n_go + ["觀察"] * n_watch + ["無訊號"] * n_rest
    df = pd.DataFrame({"股票": [f"{1000 + i}.TW" for i in range(len(sig))], "訊號判斷": sig,
                       "評分": list(range(len(sig), 0, -1)), "距一年高點%": [95.0] * len(sig),
                       "收盤價": [float("nan") if i == 0 else 10.5 + i for i in range(len(sig))]})
    summary = pd.DataFrame([{"掃描股票數": len(sig), "進場檔數": n_go, "觀察檔數": n_watch}])
    return {"df": df, "summary": summary, "failed_df": pd.DataFrame(), "elapsed_sec": 12.34,
            "market_state": {"regime": "bull", "label": "多頭", "when": pd.Timestamp("2026-11-20")},
            "scan_cache": {"x": 1}, **(extra or {})}


class FakeStore:
    def __init__(self):
        self.data = {}

    def kv_set(self, owner, key, value):
        self.data[(owner, key)] = value
        return True

    def load_holdings(self, owner):
        return pd.DataFrame({"股票代號": ["1001", "9999"]})


@pytest.fixture
def fake(monkeypatch):
    s = FakeStore()
    monkeypatch.setattr(jobs, "store", s)
    monkeypatch.setattr(jobs, "build_rulebook", lambda df, cache_dir, holding_codes=(): {
        "candidates": [{"code": "1001"}], "holdings": [{"code": c} for c in holding_codes], "month": "2026-10"})
    return s


def test_payload_keeps_only_signals_and_is_json_safe():
    p = build_payload(_result(), "breakout", "twse-common", at="2026-11-23T15:40:00")
    assert p["n_total"] == 8 and p["n_kept"] == 3
    assert {r["訊號判斷"] for r in p["rows"]} == {"進場", "觀察"}
    assert p["rows"][0]["收盤價"] is None                      # NaN → null，不是字串 "nan"
    assert p["market_state"]["when"].startswith("2026-11-20")
    import json
    json.dumps(p)


def test_payload_caps_rows():
    p = build_payload(_result(n_go=300, n_watch=0, n_rest=0), "breakout", "twse")
    assert p["n_kept"] == jobs.MAX_ROWS and len(p["rows"]) == jobs.MAX_ROWS
    assert p["rows"][0]["評分"] >= p["rows"][-1]["評分"]        # 保留評分最高的


def test_payload_with_no_signals():
    r = payload_to_result(build_payload(_result(0, 0, 4), "early", "twse"))
    assert len(r["df"]) == 0 and r["ohlc_map"] == {} and r["failed_df"].empty
    assert int(r["summary"].iloc[0]["掃描股票數"]) == 4


def test_roundtrip_to_app_result():
    r = payload_to_result(build_payload(_result(), "breakout", "twse"))
    assert len(r["df"]) == 3 and int(r["summary"].iloc[0]["進場檔數"]) == 2 and r["elapsed_sec"] == 12.3


def test_job_downloads_once_and_saves_each_mode(fake):
    calls = []

    def scan(cfg, items=None, cached=None, progress_cb=None):
        calls.append((cfg["strategy"]["mode"], items is not None, cached is not None))
        return _result()

    out = run_scan_job(load_config("config.yaml"), {"total_capital": 500_000}, "twse-common", ["breakout", "ambush"],
                       scan=scan, items_fn=lambda kind: [{"code": "1001", "company_name": "甲"}])
    assert calls == [("breakout", True, False), ("ambush", False, True)]      # 第二個模式用快取，不重抓
    assert set(out) == {"breakout", "ambush", "rulebook"}
    assert ("me", "job_scan:breakout") in fake.data and ("me", "job_scan:ambush") in fake.data
    assert fake.data[("me", "job_rulebook")]["holdings"] == [{"code": "1001"}, {"code": "9999"}]


def test_prefs_flow_into_config(fake):
    seen = {}

    def scan(cfg, items=None, cached=None, progress_cb=None):
        seen["cap"] = cfg["position_sizing"]["total_capital"]
        return _result()

    run_scan_job(load_config("config.yaml"), {"total_capital": 750_000}, modes=["breakout"], with_rulebook=False,
                 scan=scan, items_fn=lambda k: [])
    assert seen["cap"] == 750_000


def test_one_mode_failing_does_not_lose_the_others(fake):
    def scan(cfg, items=None, cached=None, progress_cb=None):
        if cfg["strategy"]["mode"] == "early":
            raise RuntimeError("boom")
        return _result()

    out = run_scan_job(load_config("config.yaml"), {}, modes=["breakout", "early", "ambush"], with_rulebook=False,
                       scan=scan, items_fn=lambda k: [])
    assert set(out) == {"breakout", "ambush"}


def test_rulebook_failure_keeps_scan_results(fake, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("rate limit")
    monkeypatch.setattr(jobs, "build_rulebook", boom)
    out = run_scan_job(load_config("config.yaml"), {}, modes=["breakout"], scan=lambda **k: _result(),
                       items_fn=lambda k: [])
    assert "breakout" in out and "rulebook" not in out


def test_unknown_modes_fall_back_to_breakout(fake):
    out = run_scan_job(load_config("config.yaml"), {}, modes=["nope"], with_rulebook=False,
                       scan=lambda **k: _result(), items_fn=lambda k: [])
    assert list(out) == ["breakout"]


def test_scheduled_requires_database_url():
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        jobs.run_scheduled("config.yaml", None)


def _wait(runner, state, timeout=3):
    end = time.time() + timeout
    while runner.snapshot()["state"] != state and time.time() < end:
        time.sleep(0.01)
    return runner.snapshot()


def test_runner_reports_progress_and_result():
    r = JobRunner()
    gate = {}

    def target(progress):
        progress(0.4, "下載中")
        while "go" not in gate:
            time.sleep(0.005)
        return {"ok": 1}

    assert r.start("測試", target)
    snap = _wait(r, "running")
    deadline = time.time() + 2
    while r.snapshot()["pct"] < 0.4 and time.time() < deadline:
        time.sleep(0.01)
    assert r.running() and r.snapshot()["msg"] == "下載中" and not r.start("另一個", lambda p: 1)   # 一次只跑一個
    gate["go"] = 1
    snap = _wait(r, "done")
    assert snap["result"] == {"ok": 1} and snap["pct"] == 1.0 and snap["finished"] >= snap["started"]


def test_runner_captures_errors_and_can_restart():
    r = JobRunner()

    def boom(progress):
        raise ValueError("壞掉了")

    r.start("x", boom)
    snap = _wait(r, "error")
    assert "壞掉了" in snap["error"] and snap["result"] is None
    assert r.start("y", lambda p: 7)
    assert _wait(r, "done")["result"] == 7
    r.clear()
    assert r.snapshot()["state"] == "idle" and r.snapshot()["result"] is None
