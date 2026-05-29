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

    above_ma20 = close > ma20
    ma5_above_ma20 = ma5 > ma20

    if above_ma20 and ma5_above_ma20:
        return {
            "regime": "bull",
            "label": "🟢 多頭",
            "position_factor": 1.0,
            "detail": f"加權 {close:.0f} > MA20 {ma20:.0f}，可正常建倉",
        }
    if not above_ma20 and not ma5_above_ma20:
        return {
            "regime": "bear",
            "label": "🔴 空頭",
            "position_factor": 0.0,
            "detail": f"加權 {close:.0f} < MA20 {ma20:.0f}，停止買入建議",
        }
    return {
        "regime": "neutral",
        "label": "🟡 中性",
        "position_factor": 0.5,
        "detail": f"加權 {close:.0f} 與 MA20 {ma20:.0f} 糾結，部位減半",
    }


def _unknown():
    return {
        "regime": "unknown",
        "label": "⚪ 未知",
        "position_factor": 1.0,
        "detail": "無法判斷大盤狀態",
    }
