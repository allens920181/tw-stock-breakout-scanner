# -*- coding: utf-8 -*-
from src.bigmoney import (
    combine_bigmoney, parse_foreign_fut_oi, score_foreign_fut,
    score_market_margin, score_twd,
)
from src.macro import merge_position_factor

_CSV = """日期,商品名稱,身份別,a,b,c,d,e,f,g,h,i,j,淨額,k
2024/05/13,臺股期貨,外資及陸資,9,1,9,1,-5,1,2,1,4,1,-14517,1
2024/05/14,臺股期貨,外資及陸資,1,1,1,1,1,1,1,1,1,1,-9000,1
2024/05/14,小型臺指期貨,外資及陸資,1,1,1,1,1,1,1,1,1,1,99999,1
2024/05/14,臺股期貨,自營商,1,1,1,1,1,1,1,1,1,1,12345,1"""


def test_parse_only_tx_foreign():
    s = parse_foreign_fut_oi(_CSV)
    assert s == [("2024/05/13", -14517), ("2024/05/14", -9000)]  # 排除小型/自營


def test_score_foreign_fut_directions():
    # 淨多且增 → 高分；淨空且減 → 低分
    hi, _ = score_foreign_fut({"latest": 25000, "prev5": 5000})
    lo, _ = score_foreign_fut({"latest": -25000, "prev5": -5000})
    assert hi > 70 and lo < 30
    assert score_foreign_fut({"latest": None})[0] == 50.0


def test_score_twd_inflow_high():
    # 台幣升值(USDTWD跌, chg<0) → 高分；貶值 → 低分
    assert score_twd({"twd_chg_pct": -2.0})[0] > 70
    assert score_twd({"twd_chg_pct": 2.0})[0] < 30
    assert score_twd({"twd_chg_pct": None})[0] == 50.0


def test_score_margin_overheat_low():
    assert score_market_margin({"latest": 110, "prev": 100})[0] < 30  # 融資+10% 過熱
    assert score_market_margin({"latest": 90, "prev": 100})[0] > 70   # 去槓桿
    assert score_market_margin({"latest": None, "prev": None})[0] == 50.0


def test_combine_factor_tiers():
    assert combine_bigmoney(80, 80, 80)[1] == 1.0
    assert combine_bigmoney(50, 50, 50)[1] == 0.75
    assert combine_bigmoney(20, 20, 20)[1] == 0.5


def test_merge_three_way_takes_min():
    tw = {"position_factor": 1.0}
    us = {"position_factor": 1.0}
    big = {"position_factor": 0.5}
    assert merge_position_factor(tw, us, big) == 0.5
    assert merge_position_factor(tw, us) == 1.0   # 向後相容
