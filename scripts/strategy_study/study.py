"""
策略實證研究：在「實際會下單的條件」下，突破策略有沒有優勢？

與 App 內建回測的差異（更貼近實盤）：
  - 只在大盤非空頭時進場（live 系統空頭暫停）；另測「僅多頭」
  - 進場當下套用品質過濾：股價 ≥ 10、20 日均量 ≥ 500 張、收盤 > MA60（皆只用當日以前資料）
  - 停損遇跳空：以開盤價成交（不是停損價）
  - 出場規則變體：固定 2R / 3R 目標；以及 live 持股規則（+1R 賣半並保本、3ATR 移動停利、10 日沒到 +1R 時間停損、最長 20 日）
  - 成本：手續費 0.1425% ×2 + 證交稅 0.3% + 滑價 0.15% ×2
時間切分：前 70% 交易日 = 樣本內（挑變體），後 30% = 樣本外（只報告，不再調）。
"""

import itertools
import json
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/tw-stock-breakout-scanner")
from twscanner.analysis.indicators import add_indicators  # noqa: E402
from twscanner.analysis.stats import bootstrap_mean_ci  # noqa: E402

DATA, TWII_CACHE, OUT = (sys.argv + ["", "", ""])[1:4]
FEE, TAX, SLIP = 0.001425, 0.003, 0.0015
W = {"breakout_with_volume": 2, "ma_bullish": 2, "kd": 1, "macd": 1}


def regime_series(cache_dir):
    import time

    from twscanner.data.prices import yf

    df = None
    for k in range(6):  # Yahoo 偶爾限流：退避重試
        df = yf.download("^TWII", period="2y", interval="1d", auto_adjust=False, progress=False)
        if df is not None and not df.empty:
            break
        time.sleep(20 * (k + 1))
    if hasattr(df.columns, "get_level_values"):
        df.columns = df.columns.get_level_values(0)
    df = add_indicators(df).dropna()
    above = df["Close"] > df["MA20"]
    ma5 = df["MA5"] > df["MA20"]
    r = pd.Series("neutral", index=pd.to_datetime(df.index).tz_localize(None))
    r[(above & ma5).values] = "bull"
    r[((~above) & (~ma5)).values] = "bear"
    return r


def prepare(df):
    d = add_indicators(df.copy())
    d.index = pd.to_datetime(d.index).tz_localize(None)
    d["high20"] = d["High"].rolling(20).max().shift(1)
    d["vol20"] = d["Volume"].rolling(20).mean()
    d["score"] = (
        W["breakout_with_volume"] * ((d["Close"] > d["high20"]) & (d["Volume"] > d["vol20"] * 1.2))
        + W["ma_bullish"] * ((d["MA5"] > d["MA20"]) & (d["MA20"] > d["MA60"]) & (d["Close"] > d["MA20"]))
        + W["kd"] * ((d["K"] > d["D"]) & (d["K"] > 70))
        + W["macd"] * (d["OSC"] > 0)
    )
    d["quality"] = (d["Close"] >= 10) & (d["vol20"] >= 500_000) & (d["Close"] > d["MA60"])
    d["low10"] = d["Low"].rolling(10).min()
    return d.dropna(subset=["MA60", "high20", "vol20", "ATR14"])


def net_r(entry, exit_px, risk):
    ne = entry * (1 + FEE + SLIP)
    nx = exit_px * (1 - FEE - TAX - SLIP)
    return (nx - ne) / risk


def simulate(d, i, entry, stop, exit_mode, hold, tp):
    """回 (exit_idx, R, reason)。i = 訊號日（以當日收盤進場）。"""
    risk = entry - stop
    n = len(d)
    if exit_mode == "fixed":
        target = entry + tp * risk
        for j in range(i + 1, min(i + 1 + hold, n)):
            o, lo, hi = d["Open"].iat[j], d["Low"].iat[j], d["High"].iat[j]
            if lo <= stop:
                return j, net_r(entry, min(o, stop), risk), "停損"
            if hi >= target:
                return j, net_r(entry, max(o, target), risk), f"+{tp}R"
        j = min(i + hold, n - 1)
        return j, net_r(entry, d["Close"].iat[j], risk), "到期"
    # live：+1R 賣半並保本、3ATR 移動停利、10 日沒到 +1R 時間停損、最長 hold 日
    half_done, realized, cur_stop, peak = False, 0.0, stop, entry
    for j in range(i + 1, min(i + 1 + hold, n)):
        o, lo, hi, c = d["Open"].iat[j], d["Low"].iat[j], d["High"].iat[j], d["Close"].iat[j]
        if lo <= cur_stop:
            px = min(o, cur_stop)
            rest = net_r(entry, px, risk)
            return j, (realized + 0.5 * rest) if half_done else rest, "停損/移動停利"
        if not half_done and hi >= entry + risk:
            half_done = True
            realized = 0.5 * net_r(entry, max(o, entry + risk), risk)
            cur_stop = max(cur_stop, entry)  # 保本
        peak = max(peak, hi)
        trail = peak - 3 * d["ATR14"].iat[j]
        if half_done:
            cur_stop = max(cur_stop, trail)
        if not half_done and (j - i) >= 10:  # 時間停損
            return j, net_r(entry, c, risk), "時間停損"
    j = min(i + hold, n - 1)
    rest = net_r(entry, d["Close"].iat[j], risk)
    return j, (realized + 0.5 * rest) if half_done else rest, "到期"


def run(stocks, regime, cfg):
    min_score, gate, stop_mode, exit_mode, hold, tp = cfg
    trades = []
    for s in stocks:
        d = s["d"]
        reg = regime.reindex(d.index, method="ffill")
        sig = (d["score"] >= min_score) & d["quality"]
        if gate == "非空頭":
            sig &= reg != "bear"
        elif gate == "僅多頭":
            sig &= reg == "bull"
        idx = np.flatnonzero(sig.values)
        nxt = 0
        for i in idx:
            if i < nxt or i >= len(d) - 1:
                continue
            entry = float(d["Close"].iat[i])
            stop = (
                max(float(d["MA20"].iat[i]), float(d["low10"].iat[i]))
                if stop_mode == "ma"
                else entry - 1.5 * float(d["ATR14"].iat[i])
            )
            if not (entry > stop) or (entry - stop) / entry < 0.02:  # live：停損距離 ≥ 2%
                continue
            j, r, why = simulate(d, i, entry, stop, exit_mode, hold, tp)
            trades.append(
                {"symbol": s["symbol"], "date": d.index[i], "r": r, "why": why, "held": j - i, "regime": reg.iat[i]}
            )
            nxt = j + 1
    return pd.DataFrame(trades)


def stats(t):
    if t is None or t.empty:
        return {"n": 0}
    r = t["r"].dropna()
    ci = bootstrap_mean_ci(r.tolist(), n_boot=2000, ci=0.95, seed=1)
    return {
        "n": int(len(r)),
        "win%": round(float((r > 0).mean() * 100), 1),
        "E": round(float(r.mean()), 3),
        "ci": [round(ci["low"], 3), round(ci["high"], 3)],
        "avg_win": round(float(r[r > 0].mean()), 2) if (r > 0).any() else 0,
        "avg_hold": round(float(t["held"].mean()), 1),
    }


def main():
    with open(DATA, "rb") as f:
        raw = pickle.load(f)
    stocks = []
    for s in raw:
        if s["df"] is None or len(s["df"]) < 200:
            continue
        try:
            stocks.append({"symbol": s["symbol"], "d": prepare(s["df"])})
        except Exception:
            continue
    regime = regime_series(TWII_CACHE)
    all_dates = sorted({dt for s in stocks for dt in s["d"].index})
    cut = all_dates[int(len(all_dates) * 0.7)]
    print(
        f"stocks {len(stocks)}  dates {all_dates[0].date()}→{all_dates[-1].date()}  IS/OOS cut {cut.date()}", flush=True
    )
    print("regime share:", regime[regime.index >= all_dates[0]].value_counts(normalize=True).round(2).to_dict())

    grid = list(
        itertools.product([5, 6], ["無", "非空頭", "僅多頭"], ["ma", "atr"], ["fixed", "live"], [10, 20], [2.0, 3.0])
    )
    grid = [g for g in grid if not (g[3] == "live" and g[5] == 3.0)]  # live 規則沒有固定目標
    rows = []
    for k, cfg in enumerate(grid):
        t = run(stocks, regime, cfg)
        is_t = t[t["date"] < cut] if len(t) else t
        oos_t = t[t["date"] >= cut] if len(t) else t
        rows.append({"cfg": cfg, "all": stats(t), "IS": stats(is_t), "OOS": stats(oos_t)})
        print(k + 1, len(grid), cfg, rows[-1]["IS"].get("E"), rows[-1]["OOS"].get("E"), flush=True)
    with open(OUT, "w") as f:
        json.dump(rows, f, ensure_ascii=False, default=str)


if __name__ == "__main__":
    main()
