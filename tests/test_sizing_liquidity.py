# -*- coding: utf-8 -*-
from src.sizing import calc_position


def test_adv_cap_limits_position():
    base = calc_position(100, 95, 10_000_000, 0.01, max_position_pct=1.0)
    capped = calc_position(100, 95, 10_000_000, 0.01, max_position_pct=1.0,
                           adv_shares=50000, max_adv_pct=0.10)
    assert base["suggested_lots"] == 20          # 不限縮
    assert capped["suggested_lots"] == 5          # 50000×10%/1000 = 5 張
    assert "流動性" in capped["warning"]


def test_adv_cap_disabled_when_none():
    a = calc_position(100, 95, 10_000_000, 0.01, max_position_pct=1.0,
                      adv_shares=None, max_adv_pct=0.10)
    b = calc_position(100, 95, 10_000_000, 0.01, max_position_pct=1.0,
                      adv_shares=50000, max_adv_pct=0)
    assert a["suggested_lots"] == 20 and b["suggested_lots"] == 20


def test_adv_cap_noop_when_liquid():
    # 日均量很大 → 不該限縮
    c = calc_position(100, 95, 10_000_000, 0.01, max_position_pct=1.0,
                      adv_shares=10_000_000, max_adv_pct=0.10)
    assert c["suggested_lots"] == 20
