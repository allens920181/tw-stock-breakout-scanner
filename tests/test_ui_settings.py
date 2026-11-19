"""側欄設定 → 掃描 cfg 的純函式（不需 Streamlit runtime）。"""
from twscanner.core.config import load_config
from twscanner.ui.settings import build_run_config


def _base():
    return load_config("config.yaml")


def test_defaults_follow_base_config():
    base = _base()
    cfg = build_run_config(base, {})
    assert cfg["filters"]["min_price"] == base["filters"]["min_price"]
    assert cfg["filters"]["min_risk_pct"] == base["filters"]["min_risk_pct"]
    assert cfg["scoring"]["thresholds"] == base["scoring"]["thresholds"]
    assert cfg["position_sizing"]["risk_per_trade_pct"] == base["position_sizing"]["risk_per_trade_pct"]
    assert cfg["strategy"]["mode"] == "breakout"


def test_sidebar_values_override_and_units():
    base = _base()
    ss = {
        "min_price": 20.0, "min_avg_volume": 300_000, "require_ma60": False,
        "min_risk_pct_slider": 3.0,                 # 側欄是 %，cfg 是比例
        "w_breakout": 3, "w_ma": 1, "w_turnover": 0, "w_kd": 2, "w_macd": 0, "w_rs": 4, "w_trend": 1,
        "thr_enter": 8, "thr_watch": 6,
        "total_capital": 2_000_000, "risk_pct": 1.5, "max_pos_pct": 25,
        "f_atr_mult": 2.0, "amb_rs_gate": False, "amb_min_rs": 2.5,
        "strategy_mode": "ambush", "cost_fee": 0.1425, "cost_disc": 0.6,
        "regime_thresholds": {"bull": {"enter": 6, "watch": 4}},
    }
    cfg = build_run_config(base, ss)
    assert cfg["filters"]["min_price"] == 20.0
    assert cfg["filters"]["require_above_ma60"] is False
    assert abs(cfg["filters"]["min_risk_pct"] - 0.03) < 1e-12
    assert cfg["scoring"]["weights"]["rel_strength"] == 4
    assert cfg["scoring"]["thresholds"] == {"enter": 8, "watch": 6}
    assert cfg["scoring"]["regime_thresholds"] == ss["regime_thresholds"]
    ps = cfg["position_sizing"]
    assert ps["total_capital"] == 2_000_000
    assert abs(ps["risk_per_trade_pct"] - 0.015) < 1e-12
    assert abs(ps["max_position_pct"] - 0.25) < 1e-12
    assert cfg["strategy"]["mode"] == "ambush"
    assert cfg["strategy"]["ambush"]["min_rs"] == 2.5
    assert abs(cfg["costs"]["fee_rate"] - 0.001425) < 1e-12
    assert cfg["costs"]["fee_discount"] == 0.6


def test_does_not_mutate_base():
    base = _base()
    before = repr(base)
    build_run_config(base, {"min_price": 99.0, "w_kd": 5})
    assert repr(base) == before
