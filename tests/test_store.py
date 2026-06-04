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
        {"股票代號": "1904", "公司名稱": "正隆", "成本價": 20.1, "持有股數": 1000},
        {"股票代號": "1608", "公司名稱": "華榮", "成本價": 36.38, "持有股數": 2000},
    ])
    recs = store.holdings_to_records(df)
    assert recs[0]["成本價"] == 20.1 and recs[0]["股票代號"] == "1904"
    back = store.records_to_holdings(recs)
    assert list(back.columns) == store._HOLD_COLS == ["股票代號", "公司名稱", "成本價", "持有股數"]
    assert len(back) == 2
    assert int(back.iloc[1]["持有股數"]) == 2000


def test_records_drop_legacy_columns():
    """雲端舊資料含『進場日/進場價』→ 載回時自動丟棄，只留 4 正規欄。"""
    recs = [{"股票代號": "2330", "公司名稱": "台積電", "成本價": 0,
             "持有股數": 1000, "進場日": "2026-05-01", "進場價": 999}]
    back = store.records_to_holdings(recs)
    assert list(back.columns) == ["股票代號", "公司名稱", "成本價", "持有股數"]
    assert "進場日" not in back.columns


def test_empty_roundtrip():
    assert store.holdings_to_records(pd.DataFrame()) == []
    assert len(store.records_to_holdings([])) == 0
