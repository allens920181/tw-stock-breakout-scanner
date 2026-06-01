import pandas as pd


def add_indicators(df):
    df = df.copy()
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA10"] = df["Close"].rolling(10).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()

    low = df["Low"].rolling(9).min()
    high = df["High"].rolling(9).max()
    rsv = (df["Close"] - low) / (high - low) * 100

    df["K"] = rsv.ewm(com=2).mean()
    df["D"] = df["K"].ewm(com=2).mean()

    ema12 = df["Close"].ewm(span=12).mean()
    ema26 = df["Close"].ewm(span=26).mean()

    df["DIF"] = ema12 - ema26
    df["MACD"] = df["DIF"].ewm(span=9).mean()
    df["OSC"] = df["DIF"] - df["MACD"]

    _add_atr_adx(df)

    return df


def _add_atr_adx(df, period=14):
    """ATR14（真實波幅）與 ADX14（趨勢強度）。Wilder 平滑以 EWM(alpha=1/period) 近似。"""
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)

    alpha = 1.0 / period
    atr = tr.ewm(alpha=alpha, adjust=False).mean()
    df["ATR14"] = atr

    up_move = df["High"].diff()
    down_move = -df["Low"].diff()
    plus_dm = ((up_move > down_move) & (up_move > 0)) * up_move.clip(lower=0)
    minus_dm = ((down_move > up_move) & (down_move > 0)) * down_move.clip(lower=0)

    atr_safe = atr.replace(0, pd.NA)
    plus_di = 100 * plus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_safe
    minus_di = 100 * minus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_safe

    di_sum = (plus_di + minus_di).replace(0, pd.NA)
    dx = 100 * (plus_di - minus_di).abs() / di_sum
    df["ADX14"] = dx.ewm(alpha=alpha, adjust=False).mean()

    return df
