# -*- coding: utf-8 -*-
from src.backtest import split_trades_is_oos, summarize_trades_is_oos


def _mk(n):
    return [{"entry_date": f"2024-01-{i+1:02d}", "return_pct": 1.0,
             "r_multiple": 0.5 if i % 2 else -0.5} for i in range(n)]


def test_split_ratio():
    is_t, oos_t = split_trades_is_oos(_mk(10), oos_ratio=0.3)
    assert len(is_t) == 7 and len(oos_t) == 3
    assert all(t["split"] == "OOS" for t in oos_t)
    assert all(t["split"] == "IS" for t in is_t)


def test_summarize_structure():
    r = summarize_trades_is_oos(_mk(10), oos_ratio=0.3)
    assert set(["overall", "is", "oos", "oos_ratio", "mode", "n_is", "n_oos"]) <= set(r)
    assert r["n_is"] + r["n_oos"] == 10


def test_empty_no_crash():
    r = summarize_trades_is_oos([])
    assert r["n_is"] == 0 and r["n_oos"] == 0
    assert r["oos"]["總交易數"] == 0


def test_boundary_ratios():
    is0, oos0 = split_trades_is_oos(_mk(10), oos_ratio=0.0)
    assert len(oos0) == 0 and len(is0) == 10
    is1, oos1 = split_trades_is_oos(_mk(10), oos_ratio=1.0)
    assert len(oos1) == 10 and len(is1) == 0


def test_rolling_union():
    trades = _mk(12)
    is_t, oos_t = split_trades_is_oos(trades, oos_ratio=0.34, mode="rolling", n_folds=3)
    assert len(is_t) + len(oos_t) == 12
    assert len(oos_t) > 0 and len(is_t) > 0
