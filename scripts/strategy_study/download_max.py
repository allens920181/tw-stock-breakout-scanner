"""研究用：抓上市普通股 + 0050 + 加權指數的完整歷史日線（Yahoo，2000 年起），存成 pickle。

用法：uv run python scripts/strategy_study/download_max.py OUT.pkl
輸出：{"prices": {symbol: DataFrame}, "names": {symbol: 公司名稱}}
"""
import pickle
import sys
import time
from pathlib import Path

import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from twscanner.data.universe import fetch_twse_universe  # noqa: E402


def main():
    uni = fetch_twse_universe(include_common=True, include_etf=False)
    syms = [f"{x['code']}.TW" for x in uni] + ["0050.TW", "^TWII"]
    names = {f"{x['code']}.TW": x["company_name"] for x in uni}
    res = {}
    for i in range(0, len(syms), 40):
        chunk, d = syms[i:i + 40], None
        for k in range(5):                               # Yahoo 偶爾限流：退避重試
            try:
                d = yf.download(chunk, period="max", interval="1d", auto_adjust=False, progress=False,
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
        time.sleep(2)
    with open(sys.argv[1], "wb") as f:
        pickle.dump({"prices": res, "names": names}, f)


if __name__ == "__main__":
    main()
