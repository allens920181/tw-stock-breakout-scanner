# -*- coding: utf-8 -*-
from src.sectors import annotate_group_strength, _name


def test_industry_name_map():
    assert _name("24") == "半導體"
    assert _name("01") == "水泥工業"
    assert _name("99") == "產業99"   # 未列代碼 → 回退
    assert _name("") is None


def test_group_strength():
    res = [
        {"股票": "2330.TW", "訊號判斷": "進場"},
        {"股票": "2454.TW", "訊號判斷": "觀察"},
        {"股票": "1101.TW", "訊號判斷": "進場"},
        {"股票": "9999.TW", "訊號判斷": "進場"},  # 產業未知
    ]
    sm = {"2330": "半導體", "2454": "半導體", "1101": "水泥工業"}
    annotate_group_strength(res, sm)
    by = {r["股票"]: r for r in res}
    assert by["2330.TW"]["族群強勢檔數"] == 2
    assert by["2330.TW"]["族群同步"] == "族群同步2檔"
    assert by["1101.TW"]["族群同步"] == "—"        # 只有 1 檔
    assert by["9999.TW"]["產業"] == "—"            # 未知不分組
    assert by["9999.TW"]["族群強勢檔數"] is None


def test_sector_heat_reduces_position():
    from src.sectors import apply_sector_heat
    # 半導體 4 檔進場（超過上限 3）→ 每檔降碼 ×0.75
    res = [
        {"股票": f"233{i}.TW", "訊號判斷": "進場", "產業": "半導體",
         "建議張數": 4, "進場成本": 400000, "佔資金%": 40.0}
        for i in range(4)
    ]
    apply_sector_heat(res, heat_max=3)
    for r in res:
        assert r["建議張數"] == 3        # 4 × (3/4) = 3
        assert "族群減碼" in r["部位提示"]


def test_sector_heat_no_change_under_limit():
    from src.sectors import apply_sector_heat
    res = [
        {"股票": "2330.TW", "訊號判斷": "進場", "產業": "半導體",
         "建議張數": 5, "進場成本": 500000, "佔資金%": 50.0},
        {"股票": "2454.TW", "訊號判斷": "進場", "產業": "半導體",
         "建議張數": 5, "進場成本": 500000, "佔資金%": 50.0},
    ]
    apply_sector_heat(res, heat_max=3)
    assert res[0]["建議張數"] == 5      # 2 檔 ≤ 上限 → 不降
