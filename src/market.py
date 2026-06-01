"""大盤狀態判斷（^TWII 加權指數）"""
import logging

import yfinance as yf

from . import cache as cache_mod
from .indicators import add_indicators

log = logging.getLogger(__name__)

TWII_SYMBOL = "^TWII"


def fetch_twii(period, cache_dir):
    cached = cache_mod.load_df(cache_dir, TWII_SYMBOL, "ohlc")
    if cached is not None and not cached.empty:
        return cached
    df = yf.download(
        TWII_SYMBOL, period=period, interval="1d",
        auto_adjust=False, progress=False,
    )
    if df is not None and not df.empty:
        if hasattr(df.columns, "get_level_values"):
            try:
                df.columns = df.columns.get_level_values(0)
            except Exception:
                pass
        cache_mod.save_df(cache_dir, TWII_SYMBOL, "ohlc", df)
    return df


def classify_market(period, cache_dir):
    """
    回傳 dict:
      regime: 'bull' / 'neutral' / 'bear'
      label:  '🟢 多頭' / '🟡 中性' / '🔴 空頭'
      position_factor: 1.0 / 0.5 / 0.0  → 部位調整倍率
      detail: 文字說明
    """
    try:
        df = fetch_twii(period, cache_dir)
    except Exception as e:
        log.warning("抓 ^TWII 失敗：%s", e)
        return _unknown()

    if df is None or df.empty or len(df) < 60:
        return _unknown()

    df = add_indicators(df).dropna()
    if len(df) < 5:
        return _unknown()

    latest = df.iloc[-1]
    close = float(latest["Close"])
    ma5 = float(latest["MA5"])
    ma20 = float(latest["MA20"])

    # 大盤 60 日報酬（給個股相對強度 RS 比較基準）
    ret_60d = _ret_n(df, 60)
    # Follow-Through Day：近期是否出現帶量上漲確認（轉多訊號）
    ftd = _detect_ftd(df)

    extra = {"ret_60d": ret_60d, "ftd_recent": ftd}

    above_ma20 = close > ma20
    ma5_above_ma20 = ma5 > ma20

    if above_ma20 and ma5_above_ma20:
        return {
            "regime": "bull",
            "label": "🟢 多頭",
            "position_factor": 1.0,
            "detail": f"加權 {close:.0f} > MA20 {ma20:.0f}，可正常建倉"
                      + ("（近期有 FTD 確認）" if ftd else ""),
            **extra,
        }
    if not above_ma20 and not ma5_above_ma20:
        return {
            "regime": "bear",
            "label": "🔴 空頭",
            "position_factor": 0.0,
            "detail": f"加權 {close:.0f} < MA20 {ma20:.0f}，停止買入建議",
            **extra,
        }
    return {
        "regime": "neutral",
        "label": "🟡 中性",
        "position_factor": 0.5,
        "detail": f"加權 {close:.0f} 與 MA20 {ma20:.0f} 糾結，部位減半",
        **extra,
    }


def _ret_n(df, n):
    if len(df) <= n:
        return None
    past = float(df["Close"].iloc[-(n + 1)])
    now = float(df["Close"].iloc[-1])
    if past <= 0:
        return None
    return (now / past - 1) * 100


def _detect_ftd(df, lookback=15):
    """
    Follow-Through Day（IBD 概念簡化版）：
    近 lookback 日內出現「指數上漲 ≥ 1.2% 且成交量 > 前一日」的確認日，
    且當日收盤站上 MA20 → 視為近期有轉多確認。
    """
    try:
        recent = df.iloc[-lookback:]
        if len(recent) < 3:
            return False
        chg = recent["Close"].pct_change() * 100
        vol_up = recent["Volume"] > recent["Volume"].shift(1)
        above = recent["Close"] > recent["MA20"]
        ftd = (chg >= 1.2) & vol_up & above
        return bool(ftd.any())
    except Exception:
        return False


def build_regime_map(period, cache_dir):
    """
    逐日大盤 regime 對照表（給回測分組用）。
    回傳 pandas.Series：index=DatetimeIndex（交易日），value='bull'/'neutral'/'bear'。
    規則同 classify_market：Close>MA20 且 MA5>MA20→bull；皆<→bear；其餘 neutral。
    """
    import pandas as pd
    try:
        df = fetch_twii(period, cache_dir)
        df = add_indicators(df).dropna()
        if df.empty:
            return pd.Series(dtype=object)
        above = df["Close"] > df["MA20"]
        ma5_above = df["MA5"] > df["MA20"]
        regime = pd.Series("neutral", index=pd.to_datetime(df.index))
        regime[above.values & ma5_above.values] = "bull"
        regime[(~above.values) & (~ma5_above.values)] = "bear"
        return regime
    except Exception as e:
        log.warning("build_regime_map 失敗：%s", e)
        return pd.Series(dtype=object)


def _unknown():
    return {
        "regime": "unknown",
        "label": "⚪ 未知",
        "position_factor": 1.0,
        "detail": "無法判斷大盤狀態",
    }
