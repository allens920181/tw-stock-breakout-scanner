"""美股風險偏好（NAAIM proxy）

來源：yfinance 的 VIX + SPX，合成 0–100 分風險偏好指數，
對應 position_factor 給 runner 用。

設計考量：
- 不使用 NAAIM 官網爬蟲（網站改版會壞）
- yfinance 全免費、無維護成本、相關度與 NAAIM 約 0.7~0.8
- 一天快取（不會盤中變動）
"""
import logging

import yfinance as yf

from . import cache as cache_mod

log = logging.getLogger(__name__)

VIX_SYMBOL = "^VIX"
SPX_SYMBOL = "^GSPC"


def _fetch(symbol, period, cache_dir):
    cached = cache_mod.load_df(cache_dir, symbol, "ohlc")
    if cached is not None and not cached.empty:
        return cached
    df = yf.download(
        symbol, period=period, interval="1d",
        auto_adjust=False, progress=False,
    )
    if df is not None and not df.empty:
        if hasattr(df.columns, "get_level_values"):
            try:
                df.columns = df.columns.get_level_values(0)
            except Exception:
                pass
        cache_mod.save_df(cache_dir, symbol, "ohlc", df)
    return df


def classify_us_market(period="1y", cache_dir=".cache"):
    """
    回傳 dict:
      regime: 'risk_on' / 'neutral' / 'risk_off' / 'unknown'
      label:  '多頭' / '中性' / '空頭' / '未知'
      score:  0-100
      position_factor: 1.0 / 0.5 / 0.0
      detail: 文字說明
      vix: 最近 VIX
      spx_above_ma50: bool
      spx_ma50_above_ma200: bool
      spx_20d_return: float
    """
    try:
        vix_df = _fetch(VIX_SYMBOL, period, cache_dir)
        spx_df = _fetch(SPX_SYMBOL, period, cache_dir)
    except Exception as e:
        log.warning("抓 US macro 失敗：%s", e)
        return _unknown()

    if (vix_df is None or vix_df.empty
            or spx_df is None or spx_df.empty or len(spx_df) < 210):
        return _unknown()

    # VIX 子分數（0-100，低 VIX 高分）
    vix_close = float(vix_df["Close"].iloc[-1])
    if vix_close < 14:
        vix_score = 100
    elif vix_close < 18:
        vix_score = 80
    elif vix_close < 22:
        vix_score = 60
    elif vix_close < 28:
        vix_score = 30
    else:
        vix_score = 0

    # SPX 趨勢子分數（0-100）
    spx_close = float(spx_df["Close"].iloc[-1])
    ma50 = float(spx_df["Close"].rolling(50).mean().iloc[-1])
    ma200 = float(spx_df["Close"].rolling(200).mean().iloc[-1])
    spx_above_ma50 = spx_close > ma50
    ma50_above_ma200 = ma50 > ma200

    if spx_above_ma50 and ma50_above_ma200:
        trend_score = 100   # 多頭排列
    elif spx_above_ma50 and not ma50_above_ma200:
        trend_score = 60    # 短強但未脫離長空
    elif not spx_above_ma50 and ma50_above_ma200:
        trend_score = 40    # 多頭但回測
    else:
        trend_score = 0     # 空頭排列

    # SPX 20 日動能子分數
    if len(spx_df) >= 21:
        ret20 = (spx_close / float(spx_df["Close"].iloc[-21]) - 1) * 100
    else:
        ret20 = 0
    if ret20 > 3:
        mom_score = 100
    elif ret20 > 0:
        mom_score = 70
    elif ret20 > -3:
        mom_score = 40
    else:
        mom_score = 0

    # 合成（40% VIX + 40% Trend + 20% Momentum）
    score = round(vix_score * 0.4 + trend_score * 0.4 + mom_score * 0.2, 1)

    if score >= 70:
        regime = "risk_on"
        label = "多頭"
        position_factor = 1.0
    elif score >= 40:
        regime = "neutral"
        label = "中性"
        position_factor = 0.5
    else:
        regime = "risk_off"
        label = "空頭"
        position_factor = 0.0

    detail = (
        f"風險分 {score:.0f} · VIX {vix_close:.1f} · "
        f"SPX {'>' if spx_above_ma50 else '<'} MA50 · "
        f"20d {ret20:+.1f}%"
    )

    return {
        "regime": regime,
        "label": label,
        "score": score,
        "position_factor": position_factor,
        "detail": detail,
        "vix": round(vix_close, 1),
        "spx_above_ma50": spx_above_ma50,
        "spx_ma50_above_ma200": ma50_above_ma200,
        "spx_20d_return": round(ret20, 2),
    }


def _unknown():
    return {
        "regime": "unknown",
        "label": "未知",
        "score": None,
        "position_factor": 1.0,  # 不確定時不影響部位
        "detail": "無法判斷美股狀態",
        "vix": None,
        "spx_above_ma50": None,
        "spx_ma50_above_ma200": None,
        "spx_20d_return": None,
    }


def merge_position_factor(tw_state, us_state, big_state=None):
    """min 取較保守者：任一警訊就減倉（台股 regime × 美股風險 × 大資金）"""
    tw_f = tw_state.get("position_factor", 1.0) if tw_state else 1.0
    us_f = us_state.get("position_factor", 1.0) if us_state else 1.0
    big_f = big_state.get("position_factor", 1.0) if big_state else 1.0
    return min(tw_f, us_f, big_f)
