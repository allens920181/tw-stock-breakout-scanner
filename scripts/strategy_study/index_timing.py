"""
大盤燈號擇時 vs 買進持有（10 年 ^TWII 與 00631L）。

燈號沿用系統既有定義、未調參：收盤 < MA20 且 MA5 < MA20 為空頭，空頭隔天起空手。
用法：uv run python scripts/strategy_study/index_timing.py OUT.json
"""
import json
import sys
import time

import pandas as pd
import yfinance as yf

COST = 0.001425 * 2 + 0.001 + 0.001 * 2   # 手續費、ETF 證交稅、滑價（來回）


def get(symbol):
    d = None
    for k in range(6):                     # Yahoo 偶爾限流：退避重試
        d = yf.download(symbol, period="10y", interval="1d", auto_adjust=True, progress=False)
        if d is not None and len(d):
            break
        time.sleep(20 * (k + 1))
    if hasattr(d.columns, "get_level_values"):
        d.columns = d.columns.get_level_values(0)
    d.index = pd.to_datetime(d.index).tz_localize(None)
    return d


def summarize(s):
    s = s.dropna()
    eq = (1 + s).cumprod()
    months = (1 + s).groupby(s.index.to_period("M")).prod() - 1
    return {"年化": round((eq.iat[-1] ** (252 / len(s)) - 1) * 100, 1),
            "最大回撤": round(((eq / eq.cummax()) - 1).min() * 100, 1),
            "月勝率": round(float((months > 0).mean()) * 100, 0),
            "最差月": round(float(months.min()) * 100, 1),
            "年報酬": {str(y): round(((1 + g).prod() - 1) * 100, 1) for y, g in s.groupby(s.index.year)}}


def evaluate(px, pos):
    r = px["Close"].pct_change()
    p = pos.reindex(r.index).ffill().fillna(0)
    trades = p.diff().abs().fillna(0)
    strat = p * r - trades * COST / 2
    return {"買進持有": summarize(r), "燈號擇時": summarize(strat),
            "持有天數比例": round(float(p.mean()) * 100, 0),
            "每年換手次數": round(float(trades.sum()) / 2 / (len(p) / 252), 1)}


def main():
    tw = get("^TWII")
    c = tw["Close"]
    ma5, ma20 = c.rolling(5).mean(), c.rolling(20).mean()
    pos = (~((c < ma20) & (ma5 < ma20))).astype(float).shift(1)   # 今天收盤判斷，明天持有
    res = {"TWII": evaluate(tw, pos), "00631L": evaluate(get("00631L.TW"), pos)}
    out = sys.argv[1] if len(sys.argv) > 1 else "index_timing.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: {m: v[m]["年化"] for m in ("買進持有", "燈號擇時")} for k, v in res.items()},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
