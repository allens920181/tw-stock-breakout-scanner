# -*- coding: utf-8 -*-
from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.earnings import days_to_earnings
from src.scoring import analyze_stock
from tests.test_scoring import CFG, _strong_uptrend_df


def test_days_to_earnings():
    assert days_to_earnings("2026-07-16", today=date(2026, 7, 14)) == 2
    assert days_to_earnings("2026-07-16", today=date(2026, 7, 18)) == -2
    assert days_to_earnings(None) is None
    assert days_to_earnings("bad") is None


def test_earnings_blackout_downgrades_entry():
    df = _strong_uptrend_df()
    cfg = {**CFG, "earnings": {"pre_days": 3, "post_days": 1, "blackout_downgrade": True}}
    soon = (date.today() + timedelta(days=2)).isoformat()
    res = analyze_stock("2330.TW", "台積電", "TW", df, shares=10_000_000_000,
                        cfg=cfg, earnings_date=soon)
    assert res["訊號判斷"] != "進場"     # 財報臨近 → 不應進場
    assert res["距財報日"] is not None


def test_earnings_far_no_effect():
    df = _strong_uptrend_df()
    far = (date.today() + timedelta(days=40)).isoformat()
    res = analyze_stock("2330.TW", "台積電", "TW", df, shares=10_000_000_000,
                        cfg=CFG, earnings_date=far)
    assert res["財報日"] == far
