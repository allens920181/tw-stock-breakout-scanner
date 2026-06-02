# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import yaml

from src.ambush import analyze_ambush
from src.scoring import analyze_stock

CFG = yaml.safe_load(open("config.yaml", encoding="utf-8"))


def _ambush_df(n=160):
    """前段整理（窄幅+量縮）→ 接近20日高未突破，模擬潛伏型態"""
    base = 100 + np.sin(np.linspace(0, 6, n)) * 1.5  # 窄幅震盪
    base[-1] = 101.5  # 收在接近高點但未破
    vol = np.concatenate([np.full(n - 5, 2_000_000), np.full(5, 1_200_000)])  # 近期量縮
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "Open": base, "High": base + 0.8, "Low": base - 0.8,
        "Close": base, "Volume": vol,
    }, index=idx)


def test_ambush_runs_and_schema():
    df = _ambush_df()
    res = analyze_ambush("2330.TW", "台積電", "TW", df, shares=5_000_000_000,
                         cfg=CFG, chips={"inst_net_lots": 3000, "foreign_net_lots": 2000,
                                         "inst_buy_streak": 2})
    # 必要欄位齊全（前端共用）
    for col in ["綜合評級", "操作建議", "進場參考價", "停損價", "訊號判斷",
                "進場類型", "評分顯示", "籌碼確認"]:
        assert col in res
    assert res["進場類型"] == "潛伏"
    assert res["訊號判斷"] in ("進場", "觀察", "不操作", "無法分析")


def test_ambush_detects_accumulation():
    df = _ambush_df()
    res = analyze_ambush("2330.TW", "x", "TW", df, shares=5_000_000_000, cfg=CFG,
                         chips={"inst_net_lots": 5000, "foreign_net_lots": 3000})
    assert res["法人吸籌"] is True


def test_early_mode_downgrades_stale_breakout():
    # 大漲一段的突破：early 模式應因「非新鮮/過度延伸」降級，breakout 模式可能仍進場
    n = 160
    close = np.linspace(40, 140, n)
    df = pd.DataFrame({
        "Open": close, "High": close + 1, "Low": close - 1, "Close": close,
        "Volume": np.concatenate([np.full(n - 1, 1e6), [5e6]]),
    }, index=pd.date_range("2024-01-01", periods=n, freq="B"))
    cfg_b = {**CFG, "strategy": {**CFG["strategy"], "mode": "breakout"}}
    cfg_e = {**CFG, "strategy": {**CFG["strategy"], "mode": "early"}}
    rb = analyze_stock("x", "x", "TW", df.copy(), shares=1e10, cfg=cfg_b)
    re = analyze_stock("x", "x", "TW", df.copy(), shares=1e10, cfg=cfg_e)
    # early 不會比 breakout 更激進（訊號不更強）
    rank = {"進場": 2, "觀察": 1, "不操作": 0, "無法分析": -1}
    assert rank[re["訊號判斷"]] <= rank[rb["訊號判斷"]]
