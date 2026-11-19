"""技術指標（純計算）：MA / KD / MACD / ATR / ADX 等，輸入輸出皆為 DataFrame。"""
import numpy as np
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
    plus_dm = (((up_move > down_move) & (up_move > 0)) * up_move.clip(lower=0)).astype(float)
    minus_dm = (((down_move > up_move) & (down_move > 0)) * down_move.clip(lower=0)).astype(float)

    # 用 np.nan（保持 float64）避免 pd.NA 把欄位變成 object dtype → pandas 3.0 ewm 會崩
    atr_safe = atr.replace(0, np.nan)
    plus_di = 100 * plus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_safe
    minus_di = 100 * minus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_safe

    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = (100 * (plus_di - minus_di).abs() / di_sum).astype(float)
    df["ADX14"] = dx.ewm(alpha=alpha, adjust=False).mean()

    return df


# ---------------------------------------------------------------------------
# 核心指標：距一年高點（研究：docs/research/core_indicator_2026-11.json）
# 10 年、1,033 檔：大盤非空頭時，收盤 ≥ 一年高點 90% 的股票，之後 1 個月平均跑贏可交易股，
# 9 年都成立；大盤空頭時沒有優勢。
HIGH_1Y_STRONG = 90.0
HIGH_1Y_WEAK = 70.0


def high_1y_pct(df, window=250, min_rows=200):
    """收盤價 ÷ 過去一年（約 250 個交易日）最高價 × 100；資料不足回 None。"""
    if df is None or len(df) < min_rows or "High" not in df or "Close" not in df:
        return None
    close = df["Close"].dropna()
    high = df["High"].dropna().iloc[-window:]
    if close.empty or high.empty:
        return None
    top = float(high.max())
    return round(float(close.iloc[-1]) / top * 100, 1) if top > 0 else None


def high_1y_zone(pct):
    """強勢區（≥ 90%）/ 中間 / 弱勢區（< 70%）。"""
    if pct is None or pct != pct:
        return "資料不足"
    if pct >= HIGH_1Y_STRONG:
        return "強勢區"
    if pct >= HIGH_1Y_WEAK:
        return "中間"
    return "弱勢區"
