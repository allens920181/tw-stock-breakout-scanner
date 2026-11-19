"""研究用：抓上市普通股 2 年日線（獨立快取目錄），存成單一 pickle。"""

import logging
import pickle
import sys

sys.path.insert(0, "/home/user/tw-stock-breakout-scanner")
from twscanner.data.prices import resolve_markets_and_data
from twscanner.data.universe import fetch_twse_universe

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
CACHE = sys.argv[1]
OUT = sys.argv[2]
uni = fetch_twse_universe(include_common=True, include_etf=False)
items = [{"code": x["code"], "company_name": x["company_name"]} for x in uni]
print("universe", len(items), flush=True)
resolved, nf = resolve_markets_and_data(items, "2y", CACHE, chunk_size=50, chunk_sleep=2.0)
print("resolved", len(resolved), "not found", len(nf), flush=True)
with open(OUT, "wb") as f:
    pickle.dump([{"symbol": r["symbol"], "name": r["company_name"], "df": r["df"]} for r in resolved], f)
print("saved", OUT, flush=True)
