"""回測敏感度：跑多個 min_score 比較 edge"""
import pandas as pd

from .backtest import backtest_symbol, summarize_trades


def sensitivity_scan(resolved, cfg, score_range, lookback_days, hold_days,
                     progress_cb=None):
    """
    對指定股票清單，跑多個 min_score 並彙整。
    回傳 DataFrame：score | n_trades | win_rate | avg_R | expectancy | max_dd
    """
    weights = cfg["scoring"]["weights"]
    rows = []
    total_steps = len(score_range)

    for step_i, score in enumerate(score_range):
        all_trades = []
        for r in resolved:
            try:
                trades = backtest_symbol(
                    r["df"], weights, score,
                    hold_days=hold_days, lookback=lookback_days,
                )
                all_trades.extend(trades)
            except Exception:
                pass

        s = summarize_trades(all_trades)
        rows.append({
            "min_score": score,
            "總交易數": s["總交易數"],
            "勝率%": s["勝率%"],
            "平均報酬%": s["平均報酬%"],
            "平均R": s["平均R"],
            "期望值R": s["期望值R"],
            "最大回撤R": s["最大回撤R"],
        })

        if progress_cb:
            try:
                progress_cb(step_i + 1, total_steps, score)
            except Exception:
                pass

    return pd.DataFrame(rows)
