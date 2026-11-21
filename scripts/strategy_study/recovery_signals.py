"""
回升訊號與劇本線索的歷史驗證（App「止跌檢查」的依據）。

問題
  1. 大跌（距一年高點 ≥ 15%）期間，四個止跌訊號成立越多，之後是不是越好？
  2. 第一次「全部成立」的日子，之後發生什麼事？
  3. 跌到 −25% 那一天，衝擊型與衰退型大跌在可量測的線索上有什麼不同？

方法
  - 門檻全部沿用 twscanner/market/recovery.py 的常數，沒有另外調參。
  - 美股資料用「前一個美股交易日」收盤（台股開盤前就知道的資訊），避免偷看。
  - Sahm 指標是月資料、隔月初公布：往後挪 35 天才算「已知」。
  - 每 10 個交易日取一個樣本，降低重疊；樣本仍然高度相關（同一段行情），結果只能當方向參考。

資料（缺檔會自動下載到 DATA_DIR）
  yfinance：^TWII ^VIX ^SOX NVDA；FRED：SAHMREALTIME BAA10Y；FinMind：外資每日買賣超（2012 起）
  若 FRED 連不上，可手動下載 https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAA10Y 等放進 DATA_DIR。

用法
  uv run python scripts/strategy_study/recovery_signals.py DATA_DIR docs/research/recovery_2026-11.json
"""
import json
import pathlib
import sys

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from twscanner.market import recovery as R

SYMS = {"TWII": "^TWII", "VIX": "^VIX", "SOX": "^SOX", "NVDA": "NVDA"}


def _load(d, name, fetch):
    p = d / f"{name}.csv"
    if not p.exists():
        fetch().to_csv(p)
    return pd.read_csv(p, index_col=0, parse_dates=True).iloc[:, 0].dropna()


def _yf(sym):
    df = yf.download(sym, start="1994-01-01", progress=False, auto_adjust=True)
    if hasattr(df.columns, "get_level_values"):
        df.columns = df.columns.get_level_values(0)
    return df[["Close"]]


def _fred(sid):
    r = requests.get(R.macro.FRED_URL, params={"id": sid}, timeout=60)
    r.raise_for_status()
    return R.macro.parse_fred_csv(r.text).rename(sid).to_frame()


def _foreign():
    r = requests.get(R.macro.FINMIND_URL, timeout=120, params={
        "dataset": "TaiwanStockTotalInstitutionalInvestors", "start_date": "2012-01-01",
        "end_date": pd.Timestamp.today().strftime("%Y-%m-%d")})
    return R.macro.parse_finmind_foreign(r.json()).rename("foreign").to_frame()


def _known_on(s, idx, lag_days=0):
    """把序列對齊到台股交易日：只用當天之前（或挪 lag_days 天後）已知的值。"""
    s = s.copy()
    if lag_days:
        s.index = s.index + pd.Timedelta(days=lag_days)
    return s.reindex(s.index.union(idx)).ffill().reindex(idx)


def build(d):
    tw = _load(d, "TWII", lambda: _yf(SYMS["TWII"]))
    us = {k: _load(d, k, lambda k=k: _yf(SYMS[k])) for k in ("VIX", "SOX", "NVDA")}
    fo = _load(d, "foreign", _foreign)
    sahm = _load(d, "SAHMREALTIME", lambda: _fred("SAHMREALTIME"))
    baa = _load(d, "BAA10Y", lambda: _fred("BAA10Y"))
    X = pd.DataFrame({"tw": tw})
    prev = {k: v.shift(1) for k, v in us.items()}            # 前一個美股交易日
    X["vix"] = _known_on(prev["VIX"], X.index)
    X["s_vix"] = X.vix <= R.VIX_CALM
    X["s_ma"] = X.tw > X.tw.rolling(R.MA_N).mean()

    def nnl(s):
        return s.rolling(R.LOW_K).min() > s.shift(R.LOW_K).rolling(R.LOW_N - R.LOW_K).min()
    semi = nnl(us["SOX"]) & nnl(us["NVDA"]).reindex(us["SOX"].index).fillna(True)
    X["s_semi"] = _known_on(semi.shift(1).astype(float), X.index) > 0.5
    f5 = fo.rolling(R.FLOW_RECENT).sum()
    ref = fo.shift(R.FLOW_RECENT).rolling(R.FLOW_BASE).sum() / (R.FLOW_BASE / R.FLOW_RECENT)
    X["s_fo"] = ((f5 >= 0) | ((ref < 0) & (f5 > ref * 0.5))).reindex(X.index)
    X.loc[X.index < fo.index[R.FLOW_RECENT + R.FLOW_BASE], "s_fo"] = np.nan
    X["dd"] = X.tw / X.tw.rolling(250, min_periods=120).max() - 1
    for h in (20, 60, 120, 250):
        X[f"r{h}"] = (X.tw.shift(-h) / X.tw - 1) * 100
    fwd_min = X.tw[::-1].rolling(60, min_periods=1).min()[::-1].shift(-1)
    X["mae60"] = (fwd_min / X.tw - 1) * 100
    X["sahm"] = _known_on(sahm, X.index, lag_days=35)
    b = _known_on(baa.shift(1), X.index)
    X["baa"] = b
    X["baa_chg"] = b - b.shift(R.CREDIT_LOOKBACK)
    return X


def _stats(s):
    s = s.dropna(subset=["r60"]).iloc[::10]
    if not len(s):
        return {"n": 0}
    return {"n": int(len(s)), "r20": round(s.r20.mean(), 1), "r60": round(s.r60.mean(), 1),
            "up60": round((s.r60 > 0).mean() * 100), "r120": round(s.r120.mean(), 1),
            "mae60_median": round(s.mae60.median(), 1), "years": sorted({int(y) for y in s.index.year})}


def by_count(X, cols, start):
    W = X.loc[start:]
    big = W[W.dd <= R.DD_APPLY]
    cnt = big[cols].sum(axis=1)
    out = {"all": _stats(big)}
    for k in range(len(cols) + 1):
        out[f"{k}"] = _stats(big[cnt == k])
    full = big[cnt == len(cols)]
    events, last = [], None
    for t in full.index:
        if last is None or (t - last).days > 120:
            r = X.loc[t]
            events.append({"date": f"{t:%Y-%m-%d}", "dd": round(r.dd * 100),
                           **{f"r{h}": None if pd.isna(r[f"r{h}"]) else round(r[f"r{h}"], 1) for h in (20, 60, 120, 250)}})
        last = t
    out["first_all_on"] = events
    return out


def episodes(X):
    """第一次跌到 −25% 的日子（相隔一年以上）與當時的劇本線索。"""
    rows, last = [], None
    for t, v in X.dd.items():
        if v <= -0.25 and (last is None or (t - last).days > 365):
            last = t
            win = X.tw.loc[:t].iloc[-250:]
            pk_t = win.idxmax()
            after = X.tw.loc[t:]
            back = after[after >= win.max()]
            r = X.loc[t]
            rows.append({"date": f"{t:%Y-%m-%d}", "peak": f"{pk_t:%Y-%m-%d}", "days_from_peak": int((t - pk_t).days),
                         "sahm": None if pd.isna(r.sahm) else round(r.sahm, 2),
                         "baa_chg_6m": None if pd.isna(r.baa_chg) else round(r.baa_chg, 2),
                         "vix": None if pd.isna(r.vix) else round(r.vix),
                         "further_low_pct": round((after.iloc[:500].min() / r.tw - 1) * 100),
                         "months_to_recover": round((back.index[0] - t).days / 30) if len(back) else None})
    return rows


def main(data_dir, out):
    d = pathlib.Path(data_dir)
    d.mkdir(parents=True, exist_ok=True)
    X = build(d)
    res = {
        "asof": f"{X.index[-1]:%Y-%m-%d}",
        "method": __doc__.strip().splitlines()[0],
        "three_signals_1999": by_count(X, ["s_vix", "s_ma", "s_semi"], "1999-03-01"),
        "four_signals_2012": by_count(X, ["s_vix", "s_ma", "s_semi", "s_fo"], "2012-03-01"),
        "episodes_at_minus25": episodes(X),
    }
    pathlib.Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in ("three_signals_1999", "four_signals_2012"):
        print(k)
        for c, v in res[k].items():
            print(" ", c, v)
    for e in res["episodes_at_minus25"]:
        print(e)


if __name__ == "__main__":
    main(*sys.argv[1:3])
