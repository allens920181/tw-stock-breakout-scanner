# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd

from src.backtest import _apply_costs, _cost_round_trip_rate, backtest_symbol
from src.indicators import add_indicators


def _trending_df(n=160):
    close = np.linspace(40, 120, n)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "Open": close, "High": close + 1.0, "Low": close - 1.0,
        "Close": close, "Volume": np.concatenate([np.full(n - 1, 1e6), [5e6]]),
    }, index=idx)


WEIGHTS = {"breakout_with_volume": 2, "ma_bullish": 2, "kd": 1, "macd": 1}


def test_cost_round_trip_rate():
    assert _cost_round_trip_rate(None) == (0.0, 0.0)
    assert _cost_round_trip_rate({"enabled": False}) == (0.0, 0.0)
    buy, sell = _cost_round_trip_rate(
        {"enabled": True, "fee_rate": 0.001425, "tax_rate": 0.003, "fee_discount": 1.0})
    assert abs(buy - 0.001425) < 1e-9
    assert abs(sell - (0.001425 + 0.003)) < 1e-9
    buy2, _ = _cost_round_trip_rate(
        {"enabled": True, "fee_rate": 0.001425, "tax_rate": 0.003, "fee_discount": 0.6})
    assert abs(buy2 - 0.001425 * 0.6) < 1e-9


def test_apply_costs_risk_basis():
    # 分母為毛 risk，分子為淨值差
    entry, exit_price, risk = 100.0, 110.0, 5.0
    net_ret, net_r = _apply_costs(entry, exit_price, risk,
                                  {"enabled": True, "fee_rate": 0.001425, "tax_rate": 0.003})
    net_entry = 100 * (1 + 0.001425)
    net_exit = 110 * (1 - 0.001425 - 0.003)
    assert abs(net_r - (net_exit - net_entry) / 5.0) < 1e-6
    assert net_ret < 10.0  # 毛報酬 10% → 淨更低


def test_cost_disabled_equals_gross():
    df = _trending_df()
    t_none = backtest_symbol(df, WEIGHTS, 4, lookback=40, costs=None)
    t_off = backtest_symbol(df, WEIGHTS, 4, lookback=40, costs={"enabled": False})
    assert len(t_none) == len(t_off)
    for a, b in zip(t_none, t_off):
        assert a["return_pct"] == b["return_pct"]
        assert a["r_multiple"] == b["r_multiple"]


def test_cost_reduces_return():
    df = _trending_df()
    t_gross = backtest_symbol(df, WEIGHTS, 4, lookback=40, costs=None)
    t_net = backtest_symbol(df, WEIGHTS, 4, lookback=40,
                            costs={"enabled": True, "fee_rate": 0.001425, "tax_rate": 0.003})
    assert len(t_gross) == len(t_net) and len(t_gross) > 0
    for g, n in zip(t_gross, t_net):
        assert n["return_pct"] < g["return_pct"]   # 淨 < 毛
