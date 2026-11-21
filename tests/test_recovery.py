"""止跌訊號與劇本線索：純計算的邊界條件。"""
import numpy as np
import pandas as pd

from twscanner.data.macro import parse_finmind_foreign, parse_fred_csv
from twscanner.market import recovery as R


def _s(values, start="2026-01-01"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_no_new_low():
    down = _s(np.linspace(100, 50, 80))
    assert R.no_new_low(down) is False                          # 一路破底
    v = list(np.linspace(100, 50, 70)) + [55, 56, 57, 58, 59] * 2
    assert R.no_new_low(_s(v)) is True                          # 近 5 日都在低點之上
    assert R.no_new_low(_s([1, 2, 3])) is None                  # 資料不足


def test_flow_easing():
    heavy = _s([-500] * 20 + [-450] * 5)
    assert R.flow_easing(heavy)[0] is False                     # 賣超沒有縮小
    easing = _s([-500] * 20 + [-200] * 5)                       # 每 5 日 −1000 → −1000
    ok, now, ref = R.flow_easing(easing)
    assert ok is True and now == -1000 and ref == -2500
    assert R.flow_easing(_s([-500] * 20 + [100] * 5))[0] is True    # 轉買超
    assert R.flow_easing(_s([1] * 10))[0] is None


def test_signals_all_off_in_crash_and_on_after_recovery():
    crash = _s(list(np.linspace(100, 140, 200)) + list(np.linspace(140, 100, 50)))
    vix = _s([20] * 230 + [36] * 20)
    sig = R.stabilization_signals(crash, vix, crash, crash, _s([-300] * 30))
    assert [x["key"] for x in sig] == ["vix", "ma20", "semi", "foreign"]
    assert not any(x["ok"] for x in sig)
    rebound = _s(list(np.linspace(100, 140, 200)) + list(np.linspace(140, 100, 30)) + list(np.linspace(100, 125, 20)))
    sig = R.stabilization_signals(rebound, _s([22] * 250), rebound, rebound, _s([-300] * 20 + [50] * 5))
    assert all(x["ok"] for x in sig)
    assert R.summarize(sig, [])["ok"] == 4


def test_missing_data_is_none_not_error():
    sig = R.stabilization_signals(None)
    assert all(x["ok"] is None for x in sig)
    clues = R.scenario_clues(None)
    assert all(c["verdict"] is None for c in clues)
    assert R.summarize(sig, clues)["lean"].startswith("線索不足")


def test_scenario_clues():
    tw = _s(list(np.linspace(100, 140, 220)) + list(np.linspace(140, 100, 30)))       # 30 個交易日跌 29%
    sahm = pd.Series([0.1, 0.6], index=pd.to_datetime(["2026-09-01", "2026-10-01"]))
    baa = _s([1.5] * 100 + [2.2] * 100)
    c = {x["key"]: x for x in R.scenario_clues(tw, sahm, baa, tsmc_yoy=-5)}
    assert c["speed"]["verdict"] == "shock"
    assert c["sahm"]["verdict"] == "recession" and c["credit"]["verdict"] == "recession"
    assert c["revenue"]["verdict"] == "recession"
    assert R.summarize([], list(c.values()))["warn"] == 3
    calm = {x["key"]: x for x in R.scenario_clues(_s(np.linspace(100, 110, 250)), tsmc_yoy=60)}
    assert calm["speed"]["verdict"] is None and calm["revenue"]["verdict"] == "shock"


def test_parsers():
    s = parse_fred_csv("observation_date,BAA10Y\n2026-11-18,1.52\n2026-11-19,.\n2026-11-20,1.56\n")
    assert list(s.values) == [1.52, 1.56]
    js = {"data": [{"date": "2026-11-20", "name": "Foreign_Investor", "buy": 3e10, "sell": 4e10},
                   {"date": "2026-11-20", "name": "Investment_Trust", "buy": 1e9, "sell": 0}]}
    f = parse_finmind_foreign(js)
    assert f.iloc[0] == -100 and len(f) == 1
    assert parse_finmind_foreign({"data": []}) is None
