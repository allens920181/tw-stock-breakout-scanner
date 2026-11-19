"""單一假設：相對強度（近 60 日漲幅在當日品質股中前 10%）是否比隨機進場好？同過濾、同閘門、同出場。"""

import json
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, sys.argv[3])
import study as S

raw = pickle.load(open(sys.argv[1], "rb"))
stocks = [{"symbol": s["symbol"], "d": S.prepare(s["df"])} for s in raw if s["df"] is not None and len(s["df"]) >= 200]
regime = S.regime_series(sys.argv[2])
ret60 = pd.DataFrame({s["symbol"]: s["d"]["Close"].pct_change(60) for s in stocks})
qual = pd.DataFrame({s["symbol"]: s["d"]["quality"] for s in stocks}).fillna(False).astype(bool)
rank = ret60.where(qual).rank(axis=1, pct=True)  # 只在當日品質股中排名（不偷看未來）
dates = sorted(ret60.index)
cut = dates[int(len(dates) * 0.7)]
rng = np.random.default_rng(23)
out = {}
for top in (0.9,):
    for exit_mode, hold, tp in (("fixed", 20, 2.0), ("fixed", 20, 3.0), ("live", 20, 2.0)):
        for kind in ("rs", "random"):
            trades = []
            for s in stocks:
                d = s["d"]
                reg = regime.reindex(d.index, method="ffill")
                base = d["quality"] & (reg != "bear")
                rs_sig = base & (rank[s["symbol"]].reindex(d.index) >= top)
                if kind == "rs":
                    sig = rs_sig
                else:
                    sig = base & pd.Series(rng.random(len(d)) < float(rs_sig.mean()), index=d.index)
                nxt = 0
                for i in np.flatnonzero(sig.values):
                    if i < nxt or i >= len(d) - 1:
                        continue
                    entry = float(d["Close"].iat[i])
                    stop = max(float(d["MA20"].iat[i]), float(d["low10"].iat[i]))
                    if not entry > stop or (entry - stop) / entry < 0.02:
                        continue
                    j, r, why = S.simulate(d, i, entry, stop, exit_mode, hold, tp)
                    trades.append({"date": d.index[i], "r": r, "held": j - i})
                    nxt = j + 1
            t = pd.DataFrame(trades)
            k = f"top{int((1 - top) * 100)}%-{exit_mode}-{hold}-{tp}-{kind}"
            out[k] = {"IS": S.stats(t[t.date < cut]), "OOS": S.stats(t[t.date >= cut])}
            print(k, out[k], flush=True)
json.dump(out, open(sys.argv[4], "w"), ensure_ascii=False, default=str)
