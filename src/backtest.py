"""
Walk-forward 回測

對既定股票清單，在過去 N 個交易日的每一天執行掃描：
  - 取候選（強勢候選或自訂門檻）
  - 假設用「當日收盤」進場、「停損 = MA20 與近 10 日低點較高者」
  - 持有 hold_days 個交易日後（或觸發停損/+2R 目標）出場
  - 統計勝率、平均報酬、期望值、最大回撤
"""
import logging
import math

import numpy as np
import pandas as pd

from .indicators import add_indicators

log = logging.getLogger(__name__)


def _slice_until(df, idx):
    """取索引 0..idx 的子集（含）"""
    return df.iloc[: idx + 1]


def _signal_score_for_bar(sub, weights):
    """簡化的當日評分（與 scoring 邏輯一致）"""
    latest = sub.iloc[-1]
    if len(sub) < 21:
        return 0, None, None
    high_20 = sub["High"].iloc[-21:-1].max()
    vol20 = sub["Volume"].rolling(20).mean().iloc[-1]

    breakout = latest["Close"] > high_20
    vol_ok = latest["Volume"] > vol20 * 1.2
    cond_breakout_with_volume = bool(breakout and vol_ok)
    cond_ma_bullish = bool(
        latest["MA5"] > latest["MA20"] > latest["MA60"]
        and latest["Close"] > latest["MA20"]
    )
    cond_kd = bool(latest["K"] > latest["D"] and latest["K"] > 70)
    cond_macd = bool(latest["OSC"] > 0)

    # 回測時不算換手率（少資料），給 0
    score = (
        weights["breakout_with_volume"] * cond_breakout_with_volume
        + weights["ma_bullish"] * cond_ma_bullish
        + weights["kd"] * cond_kd
        + weights["macd"] * cond_macd
    )
    entry = float(latest["Close"])
    stop = max(float(latest["MA20"]), float(sub["Low"].iloc[-10:].min()))
    return score, entry, stop


def backtest_symbol(df, weights, min_score, hold_days=10, lookback=120):
    """
    對單一股票回測。回傳 list[trade dict]

    trade dict:
      entry_date, entry_price, exit_date, exit_price, exit_reason, return_pct, r_multiple, held_days
    """
    if df is None or df.empty or len(df) < 80 + lookback:
        return []

    df = add_indicators(df).dropna()
    if len(df) < lookback + 20:
        return []

    trades = []
    # 在 lookback 範圍內逐日檢查
    start = len(df) - lookback
    i = start
    while i < len(df) - 1:
        sub = _slice_until(df, i)
        score, entry, stop = _signal_score_for_bar(sub, weights)

        if score >= min_score and stop is not None and entry > stop:
            risk = entry - stop
            target_2r = entry + 2 * risk

            # 從 i+1 開始追蹤直到 hit stop / +2R / hold_days
            exit_idx = None
            exit_price = None
            exit_reason = None
            for j in range(i + 1, min(i + 1 + hold_days, len(df))):
                bar = df.iloc[j]
                low = float(bar["Low"])
                high = float(bar["High"])
                close = float(bar["Close"])

                if low <= stop:
                    exit_idx = j
                    exit_price = stop
                    exit_reason = "停損"
                    break
                if high >= target_2r:
                    exit_idx = j
                    exit_price = target_2r
                    exit_reason = "+2R"
                    break
            if exit_idx is None:
                exit_idx = min(i + hold_days, len(df) - 1)
                exit_price = float(df.iloc[exit_idx]["Close"])
                exit_reason = "時間到期"

            ret_pct = (exit_price - entry) / entry * 100
            r_mult = (exit_price - entry) / risk if risk > 0 else None

            trades.append({
                "entry_date": str(df.index[i].date()),
                "entry_price": round(entry, 2),
                "exit_date": str(df.index[exit_idx].date()),
                "exit_price": round(exit_price, 2),
                "exit_reason": exit_reason,
                "return_pct": round(ret_pct, 2),
                "r_multiple": round(r_mult, 2) if r_mult is not None else None,
                "held_days": exit_idx - i,
                "score": score,
            })

            # 避免立刻重複進場：跳到 exit
            i = exit_idx + 1
        else:
            i += 1

    return trades


def summarize_trades(all_trades):
    if not all_trades:
        return {
            "總交易數": 0, "勝率%": 0, "平均報酬%": 0,
            "平均R": 0, "期望值R": 0, "最大單筆%": 0, "最大回撤%": 0,
        }
    df = pd.DataFrame(all_trades)
    win = df[df["return_pct"] > 0]
    win_rate = len(win) / len(df) * 100

    avg_r = df["r_multiple"].mean()

    # 期望值 R = 勝率 * 平均勝 - (1-勝率) * 平均敗
    wins = df[df["r_multiple"] > 0]["r_multiple"]
    losses = df[df["r_multiple"] <= 0]["r_multiple"]
    avg_win = wins.mean() if len(wins) else 0
    avg_loss = losses.mean() if len(losses) else 0
    p = win_rate / 100
    expectancy = p * avg_win + (1 - p) * avg_loss

    # 最大回撤（累積 R）
    eq = df["r_multiple"].fillna(0).cumsum()
    peak = eq.cummax()
    dd = (eq - peak)
    max_dd = abs(dd.min()) if len(dd) else 0

    return {
        "總交易數": len(df),
        "勝率%": round(win_rate, 1),
        "平均報酬%": round(df["return_pct"].mean(), 2),
        "平均R": round(avg_r if not math.isnan(avg_r) else 0, 2),
        "期望值R": round(expectancy, 2),
        "最大單筆%": round(df["return_pct"].max(), 2),
        "最大回撤R": round(max_dd, 2),
    }
