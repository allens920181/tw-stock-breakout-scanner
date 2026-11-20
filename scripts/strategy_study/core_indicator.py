"""
核心指標研究：在同一套方法下比較 8 個候選指標，找出最值得用的一個。

方法
- 範圍：目前上市普通股 10 年日線（只含仍上市者，有存活者偏差；比較「相對強弱」影響較小）
- 每 5 個交易日排名一次，只看可交易股（股價 ≥ 10、20 日均量 ≥ 500 張）
- 隔天收盤才買（避免用收盤價當天成交的樂觀假設），看之後 20 個交易日（約 1 個月）含息報酬
- 指標前 20% 減全體平均 = 超額報酬；t 值以 20 日報酬重疊 4 倍調整
- 大盤空頭：加權指數收盤 < MA20 且 MA5 < MA20（系統既有定義，未調參）

用法：
  uv run python scripts/strategy_study/core_indicator.py PRICES.pkl OUT.json
  PRICES.pkl = {symbol: DataFrame(Open/High/Low/Close/Adj Close/Volume)}，可用 download10y.py 產生
"""
import json
import pickle
import sys
import time

import numpy as np
import pandas as pd
import yfinance as yf

COST = 0.001425 * 2 + 0.003 + 0.0015 * 2           # 手續費×2、證交稅、滑價×2（來回 0.885%）
HOLD = 20
STEP = 5
THRESHOLDS = (0.85, 0.90, 0.95)


def load(path):
    raw = pickle.load(open(path, "rb"))
    frames = {}
    for col in ("Close", "Adj Close", "High", "Volume"):
        x = pd.DataFrame({k: v[col] for k, v in raw.items()})
        x.index = pd.to_datetime(x.index).tz_localize(None)
        frames[col] = x.sort_index()
    live = frames["Volume"] > 0
    return (frames["Close"].where(live), frames["Adj Close"].where(live), frames["High"], frames["Volume"])


def bear_series(index):
    tw = None
    for k in range(6):                                  # Yahoo 偶爾限流：退避重試
        tw = yf.download("^TWII", period="10y", auto_adjust=False, progress=False)
        if tw is not None and len(tw):
            break
        time.sleep(20 * (k + 1))
    if hasattr(tw.columns, "get_level_values"):
        tw.columns = tw.columns.get_level_values(0)
    tw.index = pd.to_datetime(tw.index).tz_localize(None)
    c = tw["Close"]
    ma20, ma5 = c.rolling(20).mean(), c.rolling(5).mean()
    return ((c < ma20) & (ma5 < ma20)).reindex(index, method="ffill").fillna(False)


def candidates(C, A, H, V):
    ret = A.pct_change(fill_method=None)
    ma5, ma20, ma60 = C.rolling(5).mean(), C.rolling(20).mean(), C.rolling(60).mean()
    hi20 = H.rolling(20).max().shift(1)
    breakout = (2 * ((C > hi20) & (V > V.rolling(20).mean() * 1.2))
                + 2 * ((ma5 > ma20) & (ma20 > ma60) & (C > ma20))).astype(float)
    noise = np.random.default_rng(0).random(C.shape) * 0.01          # 同分時隨機排序
    return {
        "距一年高點": C / H.rolling(250).max(),
        "系統突破分數": breakout + noise,
        "中期動能（6 個月漲幅）": A.shift(5) / A.shift(125) - 1,
        "站上季線幅度": C / ma60 - 1,
        "短期動能（1 個月漲幅）": A / A.shift(20) - 1,
        "量能放大": V.rolling(5).mean() / V.rolling(60).mean(),
        "低波動": -ret.rolling(60).std(),
        "短期反轉（1 個月跌深）": -(A / A.shift(20) - 1),
    }


def evaluate(f, fwd, tradable, bear, dates):
    rows = []
    for d in dates:
        ok = tradable.loc[d] & f.loc[d].notna() & fwd.loc[d].notna()
        if ok.sum() < 100:
            continue
        x, y = f.loc[d][ok], fwd.loc[d][ok]
        q = x.rank(pct=True, method="first")
        rows.append({"date": d, "bear": bool(bear.loc[d]), "avg": y.mean(),
                     "spread": y[q > 0.8].mean() - y.mean(),
                     "quint": [y[(q > a) & (q <= a + 0.2)].mean() - y.mean() for a in (0, .2, .4, .6, .8)]})
    return pd.DataFrame(rows)


def summarize(r):
    sp = r["spread"]
    years = sp.groupby(r["date"].dt.year).mean()
    return {"excess_pct": round(sp.mean() * 100, 2),
            "t": round(sp.mean() / (sp.std() / np.sqrt(len(sp) / (HOLD / STEP))), 2),
            "years_pos": int((years > 0).sum()), "years": int(len(years)),
            "quintiles_pct": [round(v * 100, 2) for v in np.mean(r["quint"].tolist(), axis=0)]}


def main():
    C, A, H, V = load(sys.argv[1])
    tradable = (C >= 10) & (V.rolling(20).mean() >= 500_000)
    fwd = A.shift(-(HOLD + 1)) / A.shift(-1) - 1        # 隔天收盤買、持有 20 日
    bear = bear_series(C.index)
    dates = C.index[260:-(HOLD + 2):STEP]
    out = {"as_of": str(C.index[-1].date()), "period": f"{dates[0].date()} → {dates[-1].date()}",
           "stocks": int(C.shape[1]), "weeks": len(dates), "cost_pct": round(COST * 100, 3), "ranking": []}

    for name, f in candidates(C, A, H, V).items():
        r = evaluate(f, fwd, tradable, bear, dates)
        row = {"name": name, "all": summarize(r), "non_bear": summarize(r[~r["bear"]]),
               "bear": summarize(r[r["bear"]])}
        out["ranking"].append(row)
        print(name, row["all"]["excess_pct"], row["all"]["t"], row["non_bear"]["excess_pct"], flush=True)
    out["ranking"].sort(key=lambda x: -x["all"]["t"])

    # 實用門檻：收盤 ≥ 一年高點的 N%
    f = C / H.rolling(250).max()
    rows = []
    for d in dates:
        ok = tradable.loc[d] & f.loc[d].notna() & fwd.loc[d].notna()
        x, y = f.loc[d][ok], fwd.loc[d][ok]
        rows.append({"date": d, "bear": bool(bear.loc[d]), "all": y.mean(), "low": y[x < 0.7].mean(),
                     **{f"t{int(t * 100)}": y[x >= t].mean() for t in THRESHOLDS},
                     "n90": int((x >= 0.9).sum())})
    t = pd.DataFrame(rows)
    out["threshold"] = {}
    for label, sub in (("all", t), ("non_bear", t[~t["bear"]]), ("bear", t[t["bear"]])):
        net = {k: round((sub[k].mean() - COST) * 100, 2) for k in ("all", "low", "t85", "t90", "t95")}
        net |= {"beat_avg_pct": round(float((sub["t90"] > sub["all"]).mean()) * 100, 0),
                "positive_pct": round(float((sub["t90"] - COST > 0).mean()) * 100, 0),
                "avg_count": round(float(sub["n90"].mean()), 0), "weeks": int(len(sub))}
        out["threshold"][label] = net
    nb = t[~t["bear"]]
    out["yearly_non_bear"] = {str(y): {"t90": round((g["t90"].mean() - COST) * 100, 2),
                                       "all": round((g["all"].mean() - COST) * 100, 2)}
                              for y, g in nb.groupby(nb["date"].dt.year)}
    with open(sys.argv[2], "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(json.dumps(out["threshold"], ensure_ascii=False))


if __name__ == "__main__":
    main()
