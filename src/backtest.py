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


def _cost_round_trip_rate(costs):
    """回傳 (buy_rate, sell_rate)；sell_rate 含證交稅，買賣雙邊各含滑價。
    costs=None/停用 → (0, 0)。"""
    if not costs or not costs.get("enabled", False):
        return 0.0, 0.0
    fee = costs.get("fee_rate", 0.001425) * costs.get("fee_discount", 1.0)
    tax = costs.get("tax_rate", 0.003)
    slip = costs.get("slippage_pct", 0.0)   # 買貴 / 賣便宜各 slip
    return fee + slip, fee + tax + slip


def _apply_costs(entry, exit_price, risk, costs):
    """
    扣除來回成本後的 (淨報酬%, 淨R)。
    R 風險基準維持毛值 risk=entry-stop（1R 語意不漂移），成本只進分子。
    costs=None/停用 → 回毛值。
    """
    buy_rate, sell_rate = _cost_round_trip_rate(costs)
    net_entry = entry * (1 + buy_rate)
    net_exit = exit_price * (1 - sell_rate)
    net_ret_pct = (net_exit - net_entry) / net_entry * 100 if net_entry > 0 else 0.0
    net_r = (net_exit - net_entry) / risk if risk > 0 else None
    return net_ret_pct, net_r


def _signal_score_for_bar(sub, weights, stop_mode="ma", atr_mult=None):
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
    if stop_mode == "atr" and "ATR14" in sub.columns:
        atr = float(latest["ATR14"])
        m = atr_mult if atr_mult is not None else 1.5
        stop = entry - atr * m if (atr == atr and atr > 0) else None
    else:
        stop = max(float(latest["MA20"]), float(sub["Low"].iloc[-10:].min()))
    return score, entry, stop


def _regime_at(regime_map, entry_date_str):
    """用 entry_date（字串）對 regime_map（Series）做 asof 取值；無則 'unknown'。"""
    if regime_map is None or len(regime_map) == 0:
        return "unknown"
    try:
        import pandas as pd
        dt = pd.to_datetime(entry_date_str)
        val = regime_map.asof(dt)
        return val if isinstance(val, str) else "unknown"
    except Exception:
        return "unknown"


def backtest_symbol(df, weights, min_score, hold_days=10, lookback=120, costs=None,
                    regime_map=None, stop_mode="ma", atr_mult=None, tp_mult=2.0):
    """
    對單一股票回測。回傳 list[trade dict]
    costs: dict（含 enabled/fee_rate/tax_rate/fee_discount）或 None=不計成本（向後相容）
    regime_map: pandas.Series（date→regime）或 None；標記每筆 trade['regime']
    stop_mode: 'ma'（預設，等價現行 max(MA20,low10)）或 'atr'（entry-ATR×atr_mult）
    tp_mult: 停利倍數（target = entry + tp_mult×risk），預設 2.0 等價現行 +2R

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
        score, entry, stop = _signal_score_for_bar(sub, weights, stop_mode, atr_mult)

        if score >= min_score and stop is not None and entry > stop:
            risk = entry - stop
            target_2r = entry + tp_mult * risk

            # 從 i+1 開始追蹤直到 hit stop / 停利 / hold_days
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

            ret_pct, r_mult = _apply_costs(entry, exit_price, risk, costs)

            entry_date_str = str(df.index[i].date())
            trades.append({
                "entry_date": entry_date_str,
                "regime": _regime_at(regime_map, entry_date_str),
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


def summarize_by_regime(all_trades, cfg=None):
    """依 trade['regime'] 分組，各組呼叫 summarize_trades。回 DataFrame。"""
    if not all_trades:
        return pd.DataFrame()
    labels = {"bull": "🟢 多頭", "neutral": "🟡 中性", "bear": "🔴 空頭", "unknown": "⚪ 未知"}
    groups = {}
    for t in all_trades:
        groups.setdefault(t.get("regime", "unknown"), []).append(t)
    rows = []
    for reg in ["bull", "neutral", "bear", "unknown"]:
        if reg not in groups:
            continue
        s = summarize_trades(groups[reg], cfg)
        rows.append({
            "regime": reg, "大盤狀態": labels.get(reg, reg),
            "總交易數": s["總交易數"], "勝率%": s["勝率%"],
            "平均R": s["平均R"], "期望值R": s["期望值R"],
            "最大回撤R": s["最大回撤R"],
        })
    return pd.DataFrame(rows)


def split_trades_is_oos(all_trades, oos_ratio=0.3, mode="ratio", n_folds=3):
    """
    依進場日 entry_date 時間序，把交易切成 in-sample(IS) / out-of-sample(OOS)。
    就地標 t['split']。回傳 (is_trades, oos_trades)。
    """
    if not all_trades:
        return [], []
    ts = sorted(all_trades, key=lambda t: str(t.get("entry_date", "")))
    n = len(ts)
    is_t, oos_t = [], []

    if mode == "rolling" and n_folds > 1:
        # 每折前段 IS、後段 OOS，依全域分位切
        fold = n / n_folds
        for i, t in enumerate(ts):
            pos_in_fold = (i % fold) / fold if fold > 0 else 0
            if pos_in_fold >= (1 - oos_ratio):
                t["split"] = "OOS"; oos_t.append(t)
            else:
                t["split"] = "IS"; is_t.append(t)
    else:
        cut = int(round(n * (1 - oos_ratio)))
        for i, t in enumerate(ts):
            if i >= cut:
                t["split"] = "OOS"; oos_t.append(t)
            else:
                t["split"] = "IS"; is_t.append(t)
    return is_t, oos_t


def summarize_trades_is_oos(all_trades, cfg=None, oos_ratio=0.3, mode="ratio", n_folds=3):
    """回 {'overall','is','oos','oos_ratio','mode','n_is','n_oos'}。"""
    is_t, oos_t = split_trades_is_oos(all_trades, oos_ratio, mode, n_folds)
    return {
        "overall": summarize_trades(all_trades, cfg),
        "is": summarize_trades(is_t, cfg),
        "oos": summarize_trades(oos_t, cfg),
        "oos_ratio": oos_ratio,
        "mode": mode,
        "n_is": len(is_t),
        "n_oos": len(oos_t),
    }


def summarize_trades(all_trades, cfg=None):
    if not all_trades:
        return {
            "總交易數": 0, "勝率%": 0, "平均報酬%": 0,
            "平均R": 0, "期望值R": 0, "最大單筆%": 0, "最大回撤R": 0,
            "期望值R_CI下界": 0, "期望值R_CI上界": 0,
            "樣本可信度": "極度不足", "樣本警示": True, "顯著正Edge": False,
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

    # 統計顯著性：期望值 R 的 bootstrap CI + 樣本可信度
    from .stats import bootstrap_mean_ci, sample_reliability
    stats_cfg = (cfg or {}).get("stats", {})
    ci = bootstrap_mean_ci(
        df["r_multiple"].dropna().tolist(),
        n_boot=stats_cfg.get("bootstrap_n", 1000),
        ci=stats_cfg.get("ci_level", 0.95),
        seed=stats_cfg.get("seed", 42),
    )
    rel = sample_reliability(len(df), stats_cfg)

    return {
        "總交易數": len(df),
        "勝率%": round(win_rate, 1),
        "平均報酬%": round(df["return_pct"].mean(), 2),
        "平均R": round(avg_r if not math.isnan(avg_r) else 0, 2),
        "期望值R": round(expectancy, 2),
        "最大單筆%": round(df["return_pct"].max(), 2),
        "最大回撤R": round(max_dd, 2),
        "期望值R_CI下界": round(ci["low"], 2) if ci["low"] == ci["low"] else 0,
        "期望值R_CI上界": round(ci["high"], 2) if ci["high"] == ci["high"] else 0,
        "樣本可信度": rel["label"],
        "樣本警示": rel["warn"],
        "顯著正Edge": bool(ci["low"] > 0),
    }
