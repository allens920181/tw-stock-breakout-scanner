"""
投資組合實測：把「買哪幾檔、何時買、何時賣」寫成規則，用一個真的帳戶模擬，對照 0050。

回答三個問題
1. 只看價格（距一年高點）的規則，扣成本後贏不贏 0050？停損、大盤濾網、擇時有沒有幫助？
2. 月營收（台股每月 10 日前公布）有沒有選股能力？
3. 兩者合起來的最終規則，在兩個獨立時段、各種參數擾動下還成不成立？

用法：
  uv run python scripts/strategy_study/portfolio_study.py PRICES.pkl REVENUE_DIR OUT.json
  PRICES.pkl 用 download_max.py、REVENUE_DIR 用 download_revenue.py 產生。
"""
import glob
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portfolio_engine as pe  # noqa: E402
from portfolio_engine import Rules  # noqa: E402

A_START, SPLIT, PRE_START = "2005-01-03", "2017-12-13", "2001-06-01"
PERIODS = {"A": (A_START, "2017-12-12"), "B": (SPLIT, None), "ALL": (A_START, None)}
N, HI_BUY, HI_KEEP, SUR_KEEP = 20, 0.90, 0.80, 0.50
BENCH_ETF_FROM = "2015-01-05"


def _series(raw, sym, col):
    x = raw[sym][col].copy()
    x.index = pd.to_datetime(x.index).tz_localize(None)
    return x.dropna()


def load_revenue(folder, columns, index):
    """月營收 → 每日可用的訊號。公告期限是每月 10 日，保守起見 13 日才視為已知。"""
    rows = {}
    for fn in glob.glob(f"{folder}/*.json"):
        d = json.load(open(fn))
        if d:
            s = pd.Series({pd.Timestamp(x["date"]): x["revenue"] for x in d}, dtype=float)
            rows[os.path.basename(fn)[:-5] + ".TW"] = s[~s.index.duplicated()]
    rev = pd.DataFrame(rows).sort_index()
    rev = rev.where(rev > 0)
    r3, r12 = rev.rolling(3, min_periods=3).sum(), rev.rolling(12, min_periods=12).sum()
    yoy1 = rev / rev.shift(12) - 1
    yoy3 = r3 / r3.shift(12) - 1
    past = yoy1.shift(1).rolling(12, min_periods=8)
    monthly = {"sur": (yoy1 - past.mean()) / past.std(),          # 營收驚喜：年增率比自己過去一年高多少（標準化）
               "yoy1": yoy1, "yoy3": yoy3, "accel": yoy3 - (r12 / r12.shift(12) - 1),
               "newhigh": (r3 >= r3.rolling(36, min_periods=24).max()).astype(float).where(r3.notna())}
    out = {}
    for k, v in monthly.items():
        v = v.replace([np.inf, -np.inf], np.nan).copy()
        v.index = v.index + pd.Timedelta(days=12)
        out[k] = v.reindex(v.index.union(index)).ffill(limit=45).reindex(index).reindex(columns=columns)
    return out


def calendar(dates, day=13, every=1, phase=0):
    """每 every 個月、該月 day 日（含）之後第一個交易日換股。"""
    s, k = pd.Series(False, index=dates), 0
    for y in range(dates[0].year, dates[-1].year + 1):
        for m in range(1, 13):
            if (k + phase) % every == 0:
                j = dates.searchsorted(pd.Timestamp(y, m, day))
                if j < len(dates):
                    s.iloc[j] = True
            k += 1
    return s


def main():
    raw_all = pickle.load(open(sys.argv[1], "rb"))
    raw, names = raw_all["prices"], raw_all["names"]
    p = pe.build_panel(raw)
    dates = p.C.index
    tr = pe.tradable_mask(p)
    ret = p.A.pct_change(fill_method=None)
    twii = _series(raw, "^TWII", "Close").reindex(dates).ffill()
    etf = _series(raw, "0050.TW", "Adj Close")
    # 基準：2015 起用 0050 含息報酬；之前 Yahoo 的 0050 資料缺股息又有壞點，改用加權指數 + 每年 3.5% 股息估計
    er, tw_r = etf.pct_change().loc[BENCH_ETF_FROM:], twii.pct_change()
    bad = er.abs() > 0.11
    er[bad] = tw_r.reindex(er.index)[bad]
    pre = tw_r.loc[:er.index[0]].iloc[:-1] + 0.035 / 250
    bench = (1 + pd.concat([pre, er]).fillna(0)).cumprod().reindex(dates).ffill()
    ew = (1 + ret.where(tr.shift(1, fill_value=False)).mean(axis=1).fillna(0)).cumprod()   # 可交易股等權平均（無成本）

    hi = p.C / p.H.rolling(250, min_periods=200).max()
    vol60 = ret.rolling(60).std()
    voladj = (p.A / p.A.shift(125) - 1) / (vol60 * np.sqrt(125))
    sig = load_revenue(sys.argv[2], p.C.columns, dates)
    sur = sig["sur"]
    rank = lambda f: f.where(tr).rank(axis=1, pct=True)  # noqa: E731
    bears = {"MA20": (twii < twii.rolling(20).mean()) & (twii.rolling(5).mean() < twii.rolling(20).mean()),
             "MA60": twii < twii.rolling(60).mean(), "MA200": twii < twii.rolling(200).mean()}
    R13 = calendar(dates)

    def sim(score, rules=None, keep=None, rebal=None, bear=None, start=A_START, end=None, trd=None, seed=None):
        return pe.simulate(p, score, tr if trd is None else trd, rules or Rules(n=N), bear=bear, start=start,
                           end=end, seed=seed, keep=keep, rebal=rebal)

    def stats(eq, trades=None, st=None):
        f, e, b = pe.perf(eq), pe.compare(eq, ew), pe.compare(eq, bench)
        o = {"cagr": round(f["cagr"], 1), "mdd": round(f["mdd"], 1), "sharpe": round(f["sharpe"], 2),
             "t_vs_avg": round(e["t"], 2), "t_vs_0050": round(b["t"], 2),
             "excess_month_vs_0050": round(b["excess_month"], 2)}
        if st:
            o["turnover"] = round(st["turnover_per_year"] / 2, 1)          # 每年換手幾次（單邊）
        if trades is not None and len(trades):
            o |= {"trades": int(len(trades)), "win_pct": round(float((trades.ret > 0).mean()) * 100, 0),
                  "avg_win": round(float(trades.ret[trades.ret > 0].mean()) * 100, 1),
                  "avg_loss": round(float(trades.ret[trades.ret <= 0].mean()) * 100, 1),
                  "avg_days": round(float(trades.days.mean()), 0)}
        return o

    def by_period(score, **kw):
        out = {}
        for pn, (a, b) in PERIODS.items():
            eq, t, st = sim(score, start=a, end=b, **kw)
            out[pn] = stats(eq, t, st)
        return out

    out = {"as_of": str(dates[-1].date()), "stocks": int(p.C.shape[1]),
           "periods": {"A": f"{A_START} → 2017-12-12", "B": f"{SPLIT} → {dates[-1].date()}"},
           "cost_pct": round((pe.BUY_COST + pe.SELL_COST) * 100, 3),
           "benchmark_note": f"0050 含息：{BENCH_ETF_FROM[:4]} 年起為實際含息報酬，之前以加權指數加每年 3.5% 股息估計",
           "benchmarks": {pn: {"0050": round(pe.perf(bench.loc[a:b])["cagr"], 1),
                               "0050_mdd": round(pe.perf(bench.loc[a:b])["mdd"], 1),
                               "avg": round(pe.perf(ew.loc[a:b])["cagr"], 1)} for pn, (a, b) in PERIODS.items()}}

    # ---------- 1. 只看價格 ----------
    price_score, keep80 = voladj.where(hi >= HI_BUY), hi >= HI_KEEP
    po = {"rule": by_period(price_score, keep=keep80, rebal=R13)}
    luck = {pn: [] for pn in ("A", "B")}
    for off in range(0, 20, 2):                          # 同一規則，只差在哪一天換股
        for pn in luck:
            a, b = PERIODS[pn]
            eq, _, _ = sim(price_score, rules=Rules(n=N, step=20, offset=off), keep=keep80, start=a, end=b)
            luck[pn].append(pe.perf(eq)["cagr"])
    po["rebalance_day_luck"] = {pn: {"min": round(min(v), 1), "mean": round(float(np.mean(v)), 1),
                                     "max": round(max(v), 1)} for pn, v in luck.items()}
    odds = {}
    for h in (20, 60):                                   # 單一檔：近高股票裡任選一檔
        fwd = p.A.shift(-(h + 1)) / p.A.shift(-1) - 1
        bf = bench.shift(-(h + 1)) / bench.shift(-1) - 1
        beat, pos, med, avg = [], [], [], []
        for d in dates[dates.searchsorted(pd.Timestamp(A_START)):-(h + 2):5]:
            y = fwd.loc[d][tr.loc[d] & (hi.loc[d] >= HI_BUY) & fwd.loc[d].notna()] - (pe.BUY_COST + pe.SELL_COST)
            if len(y) >= 5:
                beat.append((y > bf.loc[d]).mean())
                pos.append((y > 0).mean())
                med.append(y.median())
                avg.append(y.mean())
        odds[f"{h}d"] = {"beat_0050_pct": round(100 * float(np.mean(beat)), 0),
                         "positive_pct": round(100 * float(np.mean(pos)), 0),
                         "median_pct": round(100 * float(np.mean(med)), 2), "mean_pct": round(100 * float(np.mean(avg)), 2)}
    po["single_stock_odds"] = odds
    zero = (hi * 0).where(hi >= HI_BUY)
    disp = {}
    for n in (3, 5, 10, 20):                             # 從近高股票隨機抽 N 檔：結果有多分散
        c, lag1 = [], []
        for seed in range(10):
            eq, _, _ = sim(zero, rules=Rules(n=n), keep=keep80, rebal=R13, seed=seed)
            c.append(pe.perf(eq)["cagr"])
            lag1.append(float(((eq.pct_change(250) - bench.reindex(eq.index).pct_change(250)).dropna() < 0).mean()))
        disp[str(n)] = {"min": round(min(c), 1), "mean": round(float(np.mean(c)), 1), "max": round(max(c), 1),
                        "lag_0050_any_year_pct": round(100 * float(np.mean(lag1)), 0)}
    po["random_n_dispersion"] = disp
    br = bench.pct_change().fillna(0)
    po["index_timing"] = {}
    for nm, b in bears.items():                          # 0050 擇時：空頭隔天出場
        posn = (~b).shift(1).fillna(True).astype(float)
        eq = (1 + br * posn - posn.diff().abs().fillna(0) * 0.003).cumprod()
        po["index_timing"][nm] = {pn: {"cagr": round(pe.perf(eq.loc[a:c])["cagr"], 1),
                                       "mdd": round(pe.perf(eq.loc[a:c])["mdd"], 1)} for pn, (a, c) in PERIODS.items()}
    out["price_only"] = po

    # ---------- 2. 月營收：橫斷面 ----------
    mdays = [d for d in dates[R13.to_numpy()] if pd.Timestamp("2004-01-01") <= d < dates[-65]]

    def xs(f, hold, cond=None):
        fwd = p.A.shift(-(hold + 1)) / p.A.shift(-1) - 1
        rows = []
        for d in mdays:
            base_ok = tr.loc[d] & fwd.loc[d].notna()
            ok = base_ok & f.loc[d].notna()
            if cond is not None:
                ok &= cond.loc[d]
            if ok.sum() < 30:
                continue
            x, y, base = f.loc[d][ok], fwd.loc[d][ok], fwd.loc[d][base_ok].mean()
            q = x.rank(pct=True, method="first")
            rows.append((d, y[q > 0.8].mean() - base, y[q <= 0.2].mean() - base))
        r = pd.DataFrame(rows, columns=["d", "top", "bot"]).set_index("d")
        res = {}
        for pn, sl in (("A", slice(None, "2017-12-12")), ("B", slice(SPLIT, None))):
            t = r.loc[sl, "top"]
            res[pn] = {"top_excess_pct": round(t.mean() * 100, 2), "bottom_excess_pct": round(r.loc[sl, "bot"].mean() * 100, 2),
                       "t": round(t.mean() / (t.std() / np.sqrt(len(t) / max(1, hold / 20))), 2), "months": int(len(t))}
        return res

    labels = {"sur": "營收驚喜", "yoy1": "單月營收年增率", "yoy3": "近 3 月營收年增率", "accel": "營收成長加速",
              "newhigh": "近 3 月營收創 3 年新高"}
    out["revenue_xs"] = {"all": [{"name": labels[k], "h20": xs(sig[k], 20), "h60": xs(sig[k], 60)} for k in labels]
                         + [{"name": "距一年高點", "h20": xs(hi, 20), "h60": xs(hi, 60)}],
                         "within_near_high": [{"name": labels[k], "h20": xs(sig[k], 20, hi >= HI_BUY),
                                               "h60": xs(sig[k], 60, hi >= HI_BUY)} for k in labels]}

    # ---------- 3. 最終規則 ----------
    score = sur.where(hi >= HI_BUY)
    keep = (hi >= HI_KEEP) & (rank(sur) >= SUR_KEEP)
    eq, trades, st = sim(score, keep=keep, rebal=R13)
    rule = {"definition": {"n": N, "buy": f"距一年高點 ≥ {HI_BUY:.0%}，依營收驚喜由高到低取前 {N} 檔，等權",
                           "sell": f"每月檢查：距一年高點 < {HI_KEEP:.0%}，或營收驚喜掉到可交易股後 {SUR_KEEP:.0%}，就換掉",
                           "when": "每月 13 日（含）之後第一個交易日收盤決定，隔天開盤成交"},
            "by_period": by_period(score, keep=keep, rebal=R13)}
    yr = pd.DataFrame({"rule": eq.resample("YE").last(), "b": bench.reindex(eq.index).resample("YE").last(),
                       "avg": ew.reindex(eq.index).resample("YE").last()})
    yr.loc[eq.index[0] - pd.Timedelta(days=1)] = [eq.iloc[0], bench.reindex(eq.index).iloc[0], ew.reindex(eq.index).iloc[0]]
    yr = yr.sort_index().pct_change().dropna() * 100
    rule["yearly"] = {str(i.year): {"rule": round(r.rule, 1), "0050": round(r.b, 1), "avg": round(r.avg, 1)}
                      for i, r in yr.iterrows()}
    rel = pd.DataFrame({"s": eq, "b": bench.reindex(eq.index)})
    rule["lag_0050_pct"] = {"1y": round(100 * float((rel.pct_change(250).eval("s - b").dropna() < 0).mean()), 0),
                            "3y": round(100 * float((rel.pct_change(750).eval("s - b").dropna() < 0).mean()), 0)}
    dd = eq / eq.cummax() - 1
    rule["longest_underwater_months"] = int(round((dd < 0).astype(int).groupby((dd == 0).cumsum()).sum().max() / 21))
    curve = pd.DataFrame({"rule": eq / eq.iloc[0], "b": rel.b / rel.b.iloc[0],
                          "avg": ew.reindex(eq.index) / ew.reindex(eq.index).iloc[0]}).resample("ME").last()
    rule["curve"] = {"dates": [str(d.date()) for d in curve.index],
                     **{k: [round(float(v), 3) for v in curve[c]] for k, c in (("rule", "rule"), ("0050", "b"), ("avg", "avg"))}}

    def row(name, **kw):
        kw.setdefault("keep", keep)
        kw.setdefault("rebal", R13)
        s = by_period(kw.pop("score", score), **kw)
        return {"name": name, **{pn: {k: s[pn][k] for k in ("cagr", "mdd", "t_vs_avg", "t_vs_0050")} for pn in s},
                "turnover": s["ALL"].get("turnover")}

    rob = [row("最終規則")]
    for day in (11, 16, 20, 25):
        rob.append(row(f"換股日改每月 {day} 日後", rebal=calendar(dates, day)))
    for ph in (0, 1):
        rob.append(row(f"每 2 個月換一次（{'單' if ph else '雙'}數月）", rebal=calendar(dates, 13, 2, ph)))
    for n in (5, 10, 30):
        rob.append(row(f"持股 {n} 檔", rules=Rules(n=n)))
    rob.append(row("買進門檻 85%", score=sur.where(hi >= 0.85)))
    rob.append(row("買進門檻 95%", score=sur.where(hi >= 0.95)))
    rob.append(row("只買營收驚喜為正的", rules=Rules(n=N, min_score=0.0)))
    rob.append(row("賣出改用固定門檻（營收驚喜 < 0）", keep=(hi >= HI_KEEP) & (sur >= 0)))
    rob.append(row("每月全部重排（不續抱）", keep=None))
    rob.append(row("只看價格續抱（不看營收）", keep=keep80))
    rob.append(row("流動性加嚴（均量 ≥ 2,000 張）", trd=pe.tradable_mask(p, min_lots=2000)))
    rob.append(row("營收改用近 3 月年增率", score=sig["yoy3"].where(hi >= HI_BUY),
                   keep=(hi >= HI_KEEP) & (rank(sig["yoy3"]) >= SUR_KEEP)))
    rule["robustness"] = rob
    add = [row("移動停損 15%", rules=Rules(n=N, trail=0.15)), row("移動停損 25%", rules=Rules(n=N, trail=0.25)),
           row("固定停損 10%", rules=Rules(n=N, stop=0.10))]
    for nm, b in bears.items():
        add.append(row(f"大盤跌破 {nm}：全部出場", rules=Rules(n=N, regime="cash"), bear=b))
        add.append(row(f"大盤跌破 {nm}：不買新的", rules=Rules(n=N, regime="no_new"), bear=b))
    rule["overlays"] = add
    fee, slip = pe.SLIP, 0.004
    pe.SLIP, pe.BUY_COST, pe.SELL_COST = slip, pe.FEE + slip, pe.FEE + pe.TAX + slip
    rule["robustness"].append(row("滑價加到每邊 0.4%"))
    pe.SLIP, pe.BUY_COST, pe.SELL_COST = fee, pe.FEE + fee, pe.FEE + pe.TAX + fee
    out["rule"] = rule

    # ---------- 4. 目前名單 ----------
    d = dates[-1]
    ok = tr.loc[d] & score.loc[d].notna()
    top = score.loc[d][ok].sort_values(ascending=False).head(N)
    out["picks"] = {"as_of": str(d.date()), "eligible": int(ok.sum()),
                    "list": [{"code": s.split(".")[0], "name": names.get(s, ""), "close": round(float(p.C.loc[d, s]), 2),
                              "hi52_pct": round(float(hi.loc[d, s]) * 100, 1), "sur": round(float(v), 2),
                              "yoy_pct": round(float(sig["yoy1"].loc[d, s]) * 100, 1)} for s, v in top.items()]}
    with open(sys.argv[3], "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(json.dumps({"benchmarks": out["benchmarks"], "rule": rule["by_period"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
