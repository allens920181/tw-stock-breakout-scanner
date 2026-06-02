# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd

from src.journal import (
    evaluate_record, log_signals, summarize_journal, load_journal, save_journal,
)
from src.holdings import _holding_alerts


def _df(prices, start="2024-01-02"):
    idx = pd.date_range(start, periods=len(prices), freq="B")
    return pd.DataFrame({
        "Open": prices, "High": [p + 1 for p in prices],
        "Low": [p - 1 for p in prices], "Close": prices,
        "Volume": [1e6] * len(prices),
    }, index=idx)


def test_evaluate_hits_target():
    rec = {"掃描日": "2024-01-01", "進場參考價": 100, "停損價": 95,
           "目標價2(+2R出清)": 110}
    df = _df([100, 102, 105, 111])  # 第4根 High=112 ≥110 → +2R
    o = evaluate_record(rec, df)
    assert o["狀態"] == "達標+2R" and o["實際R"] == 2.0


def test_evaluate_hits_stop():
    rec = {"掃描日": "2024-01-01", "進場參考價": 100, "停損價": 95,
           "目標價2(+2R出清)": 110}
    df = _df([100, 98, 93])  # Low=92 ≤95 → 停損
    o = evaluate_record(rec, df)
    assert o["狀態"] == "停損" and o["實際R"] == -1.0


def test_evaluate_open():
    rec = {"掃描日": "2024-01-01", "進場參考價": 100, "停損價": 95,
           "目標價2(+2R出清)": 110}
    df = _df([100, 101, 103])  # 未碰停損/目標 → 進行中
    o = evaluate_record(rec, df)
    assert o["狀態"] == "進行中" and o["實際R"] is not None


def test_summarize():
    ev = [
        {"狀態": "達標+2R", "實際R": 2.0},
        {"狀態": "停損", "實際R": -1.0},
        {"狀態": "進行中", "實際R": 0.5},
    ]
    s = summarize_journal(ev)
    assert s["已結案"] == 2 and s["進行中"] == 1
    assert s["勝率%"] == 50.0
    assert abs(s["已結案期望值R"] - 0.5) < 1e-9


def test_log_dedupe(tmp_path):
    p = tmp_path / "j.json"
    df = pd.DataFrame([{"訊號判斷": "進場", "股票": "1234.TW", "公司名稱": "co",
                        "進場參考價": 50, "停損價": 47}])
    assert log_signals(df, "2024-05-01", path=str(p)) == 1
    assert log_signals(df, "2024-05-01", path=str(p)) == 0   # 同日同檔不重複
    assert len(load_journal(str(p))) == 1


def test_holding_alerts():
    a = _holding_alerts({"inst_net_lots": -500}, {"yoy_pct": -30},
                        {"regime": "bear", "big_state": {"position_factor": 0.5}})
    assert any("法人轉賣" in x for x in a)
    assert any("營收年減" in x for x in a)
    assert "大盤轉空" in a and "大資金轉空" in a
    assert _holding_alerts(None, None, None) == []
