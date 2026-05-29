import numpy as np
import pandas as pd

from src.indicators import add_indicators


def _make_df(n=120, seed=0):
    rng = np.random.default_rng(seed)
    base = 100 + np.cumsum(rng.normal(0, 1, n))
    df = pd.DataFrame({
        "Open": base + rng.normal(0, 0.5, n),
        "High": base + 1,
        "Low": base - 1,
        "Close": base,
        "Volume": rng.integers(1_000_000, 5_000_000, n),
    })
    return df


def test_add_indicators_columns():
    df = add_indicators(_make_df())
    for col in ["MA5", "MA20", "MA60", "K", "D", "DIF", "MACD", "OSC"]:
        assert col in df.columns


def test_indicators_length_preserved():
    df = _make_df(100)
    out = add_indicators(df)
    assert len(out) == 100


def test_ma_relationship():
    """單純遞增序列下 MA5 > MA20 > MA60"""
    n = 200
    df = pd.DataFrame({
        "Open": np.arange(n, dtype=float),
        "High": np.arange(n, dtype=float) + 1,
        "Low": np.arange(n, dtype=float) - 1,
        "Close": np.arange(n, dtype=float),
        "Volume": np.full(n, 1_000_000),
    })
    out = add_indicators(df).iloc[-1]
    assert out["MA5"] > out["MA20"] > out["MA60"]
