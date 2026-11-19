"""
月目標規劃（純計算）。

核心等式：月損益 ≈ 每筆風險金額 × 期望值(R) × 每月筆數。
設計立場（理財規劃 + 交易紀律）：
- 目標用來「推算需要做幾筆」與「控制風險」，不是用來推高部位。
- 單月結果雜訊很大（有優勢的系統也常有一半月份虧損），以近 3 個月平均評估。
- 每月虧損達上限（預設 2R）就停手。
"""
import numpy as np


def risk_amount(capital, risk_pct):
    """每筆最多賠多少錢。risk_pct 為比例（0.01 = 1%）。"""
    return float(capital) * float(risk_pct)


def trades_needed(target, capital, risk_pct, expectancy_r):
    """達到月目標平均需要幾筆交易；期望值 ≤ 0 時無解（回 None）。"""
    r_amt = risk_amount(capital, risk_pct)
    if not expectancy_r or expectancy_r <= 0 or r_amt <= 0:
        return None
    return target / (r_amt * expectancy_r)


def simulate_months(win_rate, avg_win_r, trades_per_month, r_amount, target,
                    avg_loss_r=1.0, n=20000, seed=7):
    """
    以勝率 / 平均賺 R / 平均賠 R 模擬 n 個月的損益分佈。
    回 {mean, p_loss, p_hit, p10, p90}（金額為元）。trades_per_month 取整數（至少 1）。
    """
    k = max(1, int(round(trades_per_month)))
    rng = np.random.default_rng(seed)
    wins = rng.random((n, k)) < win_rate
    r = np.where(wins, avg_win_r, -abs(avg_loss_r)).sum(axis=1) * r_amount
    return {
        "trades": k,
        "mean": float(r.mean()),
        "p_loss": float((r < 0).mean()),
        "p_hit": float((r >= target).mean()),
        "p10": float(np.percentile(r, 10)),
        "p90": float(np.percentile(r, 90)),
    }


def plan(capital, risk_pct, target, stats=None, loss_limit_r=2.0, max_trades=8):
    """
    stats: {win_rate(0-1), avg_win_r, avg_loss_r, expectancy_r, n, source}（來自回測或實戰日誌）
    回 dict：每筆風險、每月虧損上限、需要筆數、模擬結果、一句話判斷與狀態。
    """
    r_amt = risk_amount(capital, risk_pct)
    out = {
        "risk_amount": r_amt,
        "loss_limit": r_amt * loss_limit_r,
        "loss_limit_r": loss_limit_r,
        "required_return_pct": target / capital * 100 if capital else None,
        "trades_needed": None, "sim": None, "status": "unknown", "verdict": "",
    }
    if not stats or stats.get("expectancy_r") is None:
        out["verdict"] = "還沒有策略統計：先到「策略驗證」跑一次回測，才算得出每月要做幾筆。"
        return out
    e = stats["expectancy_r"]
    n = stats.get("n") or 0
    if e <= 0:
        out["status"] = "negative"
        out["verdict"] = (f"目前策略期望值 {e:+.2f}R（{n} 筆樣本），長期是賠錢的。"
                          "先別用真錢追這個目標，用小部位或模擬累積實戰紀錄。")
        return out
    need = trades_needed(target, capital, risk_pct, e)
    out["trades_needed"] = need
    win, aw = stats.get("win_rate"), stats.get("avg_win_r")
    if win is not None and aw is not None:
        out["sim"] = simulate_months(win, aw, need, r_amt, target,
                                     avg_loss_r=stats.get("avg_loss_r", 1.0))
    small = n < 30
    if need > max_trades:
        out["status"] = "stretch"
        out["verdict"] = (f"以期望值 {e:+.2f}R，每月要做約 {need:.0f} 筆才達標，超過波段操作的合理量。"
                          "建議降低月目標或提高資金，不要提高單筆風險。")
    else:
        out["status"] = "feasible"
        out["verdict"] = f"以期望值 {e:+.2f}R、每筆風險 {r_amt:,.0f} 元，平均每月約 {need:.1f} 筆可達標。"
    if small:
        out["verdict"] += f"（樣本只有 {n} 筆，數字僅供參考）"
    return out


def month_progress(realized, realized_r, target, loss_limit_r=2.0, history=None):
    """
    本月進度。realized: 本月已實現損益（元）；realized_r: 本月已實現 R 總和。
    history: 前幾個月的已實現損益 list（新→舊），用來算近 3 個月平均。
    """
    hist = [h for h in (history or []) if h is not None][:2]
    avg3 = (realized + sum(hist)) / (1 + len(hist))
    stop = realized_r is not None and realized_r <= -abs(loss_limit_r)
    pct = realized / target * 100 if target else None
    if stop:
        status = f"本月已虧 {abs(realized_r):.1f}R，達到停手上限：本月不再開新倉，只管理持股。"
    elif realized >= target:
        status = "本月已達標。接下來的交易照規則做，不需要為了多賺而加碼。"
    elif realized >= 0:
        status = f"本月還差 {target - realized:,.0f} 元。照規則挑標的，不要因為差多少而放寬條件。"
    else:
        status = f"本月目前 {realized:,.0f} 元。虧損在上限內，照規則繼續即可。"
    return {"realized": realized, "realized_r": realized_r, "pct": pct, "avg3": avg3,
            "months_in_avg": 1 + len(hist), "stop_trading": stop, "status": status}


def stats_from_r(r_values, source):
    """一串 R 倍數 → {win_rate, avg_win_r, avg_loss_r, expectancy_r, n, source}；空的回 None。"""
    rs = [float(x) for x in r_values if x is not None and x == x]
    if not rs:
        return None
    wins = [x for x in rs if x > 0]
    losses = [x for x in rs if x <= 0]
    return {"win_rate": len(wins) / len(rs),
            "avg_win_r": sum(wins) / len(wins) if wins else 0.0,
            "avg_loss_r": -sum(losses) / len(losses) if losses else 1.0,
            "expectancy_r": sum(rs) / len(rs), "n": len(rs), "source": source}
