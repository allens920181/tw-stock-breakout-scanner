# -*- coding: utf-8 -*-
import pandas as pd
from src import store


def test_disabled_by_default():
    store.configure(None)
    assert store.is_enabled() is False
    assert store.kv_get("me", "holdings", "DEF") == "DEF"   # 停用→回預設
    assert store.kv_set("me", "holdings", [1]) is False
    assert store.save_holdings("me", pd.DataFrame()) is False
    assert store.load_holdings("me") is None


def test_holdings_roundtrip():
    df = pd.DataFrame([
        {"股票代號": "1904", "公司名稱": "正隆", "進場價": 20.1,
         "進場日": pd.Timestamp("2026-05-20"), "持有張數": 1},
        {"股票代號": "1608", "公司名稱": "華榮", "進場價": 36.38,
         "進場日": pd.Timestamp("2026-05-25"), "持有張數": 2},
    ])
    recs = store.holdings_to_records(df)
    assert recs[0]["進場日"] == "2026-05-20" and recs[0]["股票代號"] == "1904"
    back = store.records_to_holdings(recs)
    assert list(back.columns) == store._HOLD_COLS
    assert len(back) == 2
    assert str(back.iloc[1]["進場日"].date()) == "2026-05-25"
    assert float(back.iloc[0]["進場價"]) == 20.1


def test_empty_roundtrip():
    assert store.holdings_to_records(pd.DataFrame()) == []
    assert len(store.records_to_holdings([])) == 0
