"""研究用：以 2 年資料的代號清單批次抓 10 年日線，存成 {symbol: DataFrame}。

用法：uv run python scripts/strategy_study/download10y.py data2y.pkl data10y.pkl
"""
import pickle
import sys
import time

import yfinance as yf


def main():
    syms = [s["symbol"] for s in pickle.load(open(sys.argv[1], "rb"))]
    res = {}
    for i in range(0, len(syms), 50):
        chunk = syms[i:i + 50]
        d = None
        for k in range(5):                       # Yahoo 偶爾限流：退避重試
            try:
                d = yf.download(chunk, period="10y", interval="1d", auto_adjust=False, progress=False,
                                group_by="ticker", threads=True)
            except Exception as e:
                print("error", e, flush=True)
            if d is not None and len(d):
                break
            time.sleep(30 * (k + 1))
        for s in chunk:
            try:
                x = d[s].dropna(how="all")
            except Exception:
                continue
            if len(x) > 200:
                res[s] = x
        print(i + len(chunk), len(res), flush=True)
        time.sleep(3)
    with open(sys.argv[2], "wb") as f:
        pickle.dump(res, f)


if __name__ == "__main__":
    main()
