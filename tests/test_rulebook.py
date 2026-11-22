"""實證規則：營收驚喜計算、買進名單、持股檢查、名單組裝（不抓網路）。"""
import pandas as pd

from twscanner.analysis.revenue_surprise import pick_candidates, revenue_surprise, sell_check
from twscanner.data.revenue_history import fetch_many, parse_rows
from twscanner.services.rulebook import build_rulebook


def _series(growth_last, growth_past=(0.10, 0.12, 0.08, 0.11, 0.09, 0.10, 0.12, 0.08, 0.11, 0.09, 0.10, 0.12)):
    """兩年基期 100，之後 12 個月年增率 growth_past，最新一個月年增率 growth_last。"""
    rows = [(f"2024-{m:02d}", 100.0) for m in range(1, 13)]
    rows += [(f"2025-{m:02d}", 100.0 * (1 + g)) for m, g in zip(range(1, 13), growth_past)]
    rows.append(("2026-01", 100.0 * (1 + growth_past[0]) * (1 + growth_last)))
    return rows


def test_surprise_positive_when_growth_jumps():
    s = revenue_surprise(_series(0.40))
    assert s["month"] == "2026-01" and s["yoy_pct"] == 40.0
    assert s["sur"] > 5


def test_surprise_negative_when_growth_drops():
    assert revenue_surprise(_series(-0.10))["sur"] < -5


def test_surprise_needs_history():
    rows = [("2025-01", 100.0), ("2026-01", 150.0)]
    s = revenue_surprise(rows)
    assert s["yoy_pct"] == 50.0 and s["sur"] is None
    assert revenue_surprise([])["sur"] is None


def test_surprise_ignores_missing_and_flat_history():
    flat = _series(0.3, growth_past=(0.1,) * 12)               # 過去年增率完全一樣：標準差 0，不硬算
    assert revenue_surprise(flat)["sur"] is None
    assert revenue_surprise(_series(0.3) + [("2026-02", None)])["month"] == "2026-01"


def test_pick_candidates_filters_and_sorts():
    rows = [{"code": "A", "high_1y": 95, "sur": 0.5}, {"code": "B", "high_1y": 99, "sur": 2.0},
            {"code": "C", "high_1y": 85, "sur": 9.0}, {"code": "D", "high_1y": 92, "sur": None}]
    assert [r["code"] for r in pick_candidates(rows)] == ["B", "A"]
    assert [r["code"] for r in pick_candidates(rows, n=1)] == ["B"]


def test_sell_check():
    assert sell_check(95, 1.2)[0] == "續抱"
    assert sell_check(75, 1.2)[0] == "賣出"
    assert sell_check(95, -0.3)[0] == "賣出"
    assert sell_check(95, None)[0] == "資料不足"
    assert sell_check(None, 1.0)[0] == "資料不足"


def test_parse_rows_uses_revenue_month_not_announcement_date():
    rows = [{"date": "2026-02-01", "revenue_year": 2026, "revenue_month": 1, "revenue": 5},
            {"date": "2026-01-01", "revenue_year": 2025, "revenue_month": 12, "revenue": 3}, {"bad": 1}]
    assert parse_rows(rows) == [("2025-12", 3.0), ("2026-01", 5.0)]


def test_fetch_many_caches_and_stops_after_repeated_failures(tmp_path):
    calls = []

    def fake(code):
        calls.append(code)
        if code.startswith("X"):
            raise RuntimeError("limit")
        return [("2026-01", 1.0)]

    out = fetch_many(["1", "2"], str(tmp_path), fetch=fake)
    assert set(out) == {"1", "2"}
    fetch_many(["1", "2"], str(tmp_path), fetch=fake)
    assert calls == ["1", "2"]                                  # 第二次讀快取
    out = fetch_many(["X1", "X2", "X3", "X4", "X5", "X6", "3"], str(tmp_path), fetch=fake)
    assert out == {} and "X6" not in calls                      # 連續 5 次失敗就停


def test_build_rulebook():
    df = pd.DataFrame({"股票": ["1111.TW", "2222.TW", "3333.TW"], "公司名稱": ["甲", "乙", "丙"],
                       "收盤價": [50.0, 80.0, 20.0], "距一年高點%": [96.0, 91.0, 70.0]})
    hist = {"1111": _series(0.40), "2222": _series(-0.10), "3333": _series(0.40)}
    seen = {}

    def fake(codes, cache_dir, progress_cb=None):
        seen["codes"] = codes
        return {c: hist[c] for c in codes if c in hist}

    rb = build_rulebook(df, ".cache", holding_codes=["2222", "3333", "9999"], fetch=fake)
    assert seen["codes"] == ["1111", "2222", "3333", "9999"]    # 近高的 + 持股
    assert [r["code"] for r in rb["candidates"]] == ["1111", "2222"]
    assert rb["near_high"] == 2 and rb["eligible"] == 2 and rb["month"] == "2026-01"
    acts = {h["code"]: h["action"] for h in rb["holdings"]}
    assert acts == {"2222": "賣出", "3333": "賣出", "9999": "資料不足"}
    assert build_rulebook(pd.DataFrame(), ".cache") is None
