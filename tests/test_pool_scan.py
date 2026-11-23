"""run_pool_scan：資料池命中、補抓、只更新現價（不抓網路）。"""
from twscanner.services import pool_scan
from twscanner.services.pool_scan import run_pool_scan

ITEMS = [{"code": "1111", "company_name": "甲"}, {"code": "2222", "company_name": "乙"}]


def _cache(codes):
    return {"items": [{"code": c, "company_name": c} for c in codes],
            "resolved": [{"symbol": f"{c}.TW", "company_name": c, "df": None} for c in codes], "not_found": [],
            "shares_map": {f"{c}.TW": 1 for c in codes}, "price_map": {f"{c}.TW": 10.0 for c in codes},
            "earnings_map": {}, "chips_map": {}, "margin_map": {}, "revenue_map": {}, "market_state": {"regime": "bull"}}


class FakeScan:
    def __init__(self):
        self.calls = []

    def __call__(self, cfg=None, items=None, cached=None, progress_cb=None):
        self.calls.append(("download" if items is not None else "cached",
                           [i["code"] for i in items] if items is not None else [r["symbol"] for r in cached["resolved"]]))
        if progress_cb:
            progress_cb("下載", 0.5, "…")
        codes = [i["code"] for i in items] if items is not None else [r["symbol"].split(".")[0] for r in cached["resolved"]]
        return {"df": None, "summary": None, "elapsed_sec": 1, "scan_cache": _cache(codes)}


def test_empty_pool_downloads_everything_once():
    f, seen = FakeScan(), []
    out = run_pool_scan({}, ITEMS, None, progress_cb=lambda p, m: seen.append(m), scan=f)
    assert f.calls == [("download", ["1111", "2222"])]
    assert out["downloaded"] == 2 and out["reused"] == 0 and out["pool_changed"] and len(out["pool"]["resolved"]) == 2
    assert seen and seen[0].startswith("下載：")


def test_partial_pool_downloads_only_the_missing_then_reevaluates_all():
    f = FakeScan()
    pool = _cache(["1111"])
    out = run_pool_scan({}, ITEMS, pool, scan=f)
    assert f.calls[0] == ("download", ["2222"]) and f.calls[1][0] == "cached"
    assert out["reused"] == 1 and out["downloaded"] == 1
    assert len(pool["resolved"]) == 1                               # 傳進來的池子不被修改（背景執行緒不能動到 session 的資料）


def test_full_pool_with_fresh_prices_does_not_refresh():
    f = FakeScan()
    out = run_pool_scan({}, ITEMS, _cache(["1111", "2222"]), pool_age_min=5, scan=f)
    assert f.calls == [("cached", ["1111.TW", "2222.TW"])] and not out["pool_changed"] and out["downloaded"] == 0


def test_stale_prices_are_refreshed_only_when_asked(monkeypatch):
    monkeypatch.setattr(pool_scan, "refresh_prices", lambda sub, cfg: {"1111.TW": 99.0})
    stale = pool_scan.PRICE_STALE_MIN + 1
    out = run_pool_scan({}, ITEMS, _cache(["1111", "2222"]), pool_age_min=stale, scan=FakeScan())
    assert out["pool_changed"] and out["pool"]["price_map"]["1111.TW"] == 99.0 and out["pool"]["price_map"]["2222.TW"] == 10.0
    out = run_pool_scan({}, ITEMS, _cache(["1111", "2222"]), pool_age_min=stale, fresh_prices=False, scan=FakeScan())
    assert not out["pool_changed"]
