import numpy as np
import pandas as pd

from twscanner.market import flows as F


def _idx(n, start="2026-01-01"):
    return pd.bdate_range(start, periods=n)


def test_cmf_sign():
    n = 30
    idx = _idx(n)
    high = pd.Series(10.0, index=idx)
    low = pd.Series(9.0, index=idx)
    vol = pd.Series(1000.0, index=idx)
    up = F.cmf(high, low, pd.Series(9.9, index=idx), vol).iloc[-1]     # 收在高檔
    dn = F.cmf(high, low, pd.Series(9.1, index=idx), vol).iloc[-1]     # 收在低檔
    assert up > 0.5 and dn < -0.5


def test_rrg_quadrants():
    n = 60
    idx = _idx(n)
    bench = pd.Series(100.0, index=idx)
    # 持續跑贏大盤且加速 → 領先
    strong = pd.Series(100 * np.exp(np.linspace(0, 0.3, n) ** 2), index=idx)
    r = F.rrg(strong, bench).dropna().iloc[-1]
    assert F.quadrant(r["ratio"], r["mom"]) == "leading"
    # 持續跑輸且加速 → 落後
    weak = pd.Series(100 * np.exp(-np.linspace(0, 0.3, n) ** 2), index=idx)
    r = F.rrg(weak, bench).dropna().iloc[-1]
    assert F.quadrant(r["ratio"], r["mom"]) == "lagging"
    assert F.quadrant(101, 99) == "weakening"
    assert F.quadrant(99, 101) == "improving"
    assert F.quadrant(None, 100) is None


def test_sector_share_shift():
    idx = _idx(21)
    vals = pd.DataFrame({"半導體": [50.0] * 20 + [70.0], "金融": [50.0] * 20 + [30.0]}, index=idx)
    out = F.sector_share_shift(vals)
    assert out.index[0] == "半導體"
    assert out.loc["半導體", "比重變化pp"] == 20.0
    assert out.loc["金融", "比重變化pp"] == -20.0


def test_lead_lag_uses_previous_us_session():
    # 台股 d 日報酬 = 美股 d-1 日報酬 → 相關應接近 1
    rng = np.random.default_rng(0)
    idx = _idx(80)
    us_ret = rng.normal(0, 1, len(idx))
    us = pd.Series(100 * np.cumprod(1 + us_ret / 100), index=idx)
    tw_ret = np.r_[0, us_ret[:-1]]
    tw = pd.Series(100 * np.cumprod(1 + tw_ret / 100), index=idx)
    r = F.lead_lag(tw, us, window=60)
    assert r["corr"] > 0.99
    assert r["same_dir"] > 95


def test_adr_premium():
    idx = _idx(5)
    tsm = pd.Series(110.0, index=idx)
    tw = pd.Series(640.0, index=idx)          # 640×5/32 = 100 USD
    fx = pd.Series(32.0, index=idx)
    prem = F.adr_premium(tsm, tw, fx)
    assert abs(prem.iloc[-1] - 10.0) < 1e-9


def test_parse_bfi82u():
    js = {"stat": "OK", "data": [
        ["自營商(自行買賣)", "1", "1", "100,000,000"],
        ["自營商(避險)", "1", "1", "-300,000,000"],
        ["投信", "1", "1", "500,000,000"],
        ["外資及陸資(不含外資自營商)", "1", "1", "-1,000,000,000"],
        ["外資自營商", "0", "0", "200,000,000"],
        ["合計", "1", "1", "-500,000,000"],
    ]}
    out = F.parse_bfi82u(js)
    assert out == {"外資": -800_000_000.0, "投信": 500_000_000.0, "自營商": -200_000_000.0}
    assert F.parse_bfi82u({"stat": "很抱歉，沒有符合條件的資料!"}) is None


def test_parse_bfiamu_excludes_parents():
    js = {"stat": "OK", "data": [
        ["電子類指數          ", "1", "1,000", "1", "1"],
        ["半導體類指數        ", "1", "600", "1", "1"],
        ["化學生技醫療類指數  ", "1", "100", "1", "1"],
        ["金融保險類指數      ", "1", "300", "1", "1"],
    ]}
    assert F.parse_bfiamu(js) == {"半導體": 600.0, "金融保險": 300.0}


def test_sector_inst_flow():
    t86 = [{"2330": [1_000_000, 0], "2881": [0, -2_000_000], "0050": [5, 5]},
           {"2330": [1_000_000, 0]}]
    sectors = {"2330": "半導體", "2881": "金融保險"}
    close = {"2330": 1000.0, "2881": 50.0, "0050": 100.0}
    df = F.sector_inst_flow(t86, sectors, close)
    assert df.loc["半導體", "外資"] == 20.0      # 2,000,000 股 × 1000 元 = 20 億
    assert df.loc["金融保險", "投信"] == -1.0
    assert "0050" not in df.index and len(df) == 2
    assert df.index[0] == "半導體"


def test_streak_and_summary_smoke():
    inst = pd.DataFrame({"外資": [-1, 5, 3, 2], "投信": [1, 1, -1, 1], "自營商": [0, 0, 0, 0]},
                        index=pd.to_datetime(["2026-11-13", "2026-11-16", "2026-11-17", "2026-11-18"]))
    assert F._streak(inst["外資"]) == 3
    s = F.build_summary(tw={"inst": inst})
    assert any("連續 3 日買超" in x for x in s["tw"])
    assert s["us"] == [] and s["link"] == []


def test_risk_appetite_label():
    st = pd.DataFrame({"20日變化%": [1.0, 2.0, 0.5, -1.0], "站上50日線": [True, True, True, False]})
    assert F.risk_appetite_label(st)[0].startswith("🟢")
    st2 = pd.DataFrame({"20日變化%": [-1.0, -2.0, -0.5, 1.0], "站上50日線": [False, False, False, True]})
    assert F.risk_appetite_label(st2)[0].startswith("🔴")
