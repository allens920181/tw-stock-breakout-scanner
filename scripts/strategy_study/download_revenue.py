"""研究用：抓每檔股票 2002 年起的月營收（FinMind 免費 API，逐檔抓、可中斷續抓）。

用法：uv run python scripts/strategy_study/download_revenue.py PRICES.pkl OUT_DIR
輸出：OUT_DIR/{代號}.json，每筆 {"date": 公告月 1 號, "revenue": 當月營收, ...}
注意：date 是「營收月份的下個月 1 號」，實際公告在該月 10 日前（遇假日順延）。
"""
import json
import os
import pickle
import sys
import time
import urllib.parse
import urllib.request

URL = "https://api.finmindtrade.com/api/v4/data?"


def main():
    prices = pickle.load(open(sys.argv[1], "rb"))["prices"]
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    codes = [s.split(".")[0] for s in prices if s.endswith(".TW")]
    for k, c in enumerate(codes):
        fn = f"{out}/{c}.json"
        if os.path.exists(fn):
            continue
        q = urllib.parse.urlencode({"dataset": "TaiwanStockMonthRevenue", "data_id": c, "start_date": "2002-01-01"})
        while True:
            try:
                d = json.loads(urllib.request.urlopen(URL + q, timeout=40).read())
                if d.get("status") == 200:
                    json.dump(d["data"], open(fn, "w"))
                    break
                print("status", d.get("status"), d.get("msg"), flush=True)
            except Exception as e:
                print(k, c, "error", str(e)[:80], flush=True)
            time.sleep(300)                              # 免費額度用完：等 5 分鐘再試
        if k % 50 == 0:
            print(k, c, flush=True)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
