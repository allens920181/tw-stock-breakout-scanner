"""對照組：同樣的品質過濾、大盤閘門、出場規則，但進場日隨機（每檔每天同機率）。"""

import json
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, sys.argv[3])
import study as S

data, cache, out = sys.argv[1], sys.argv[2], sys.argv[4]
raw = pickle.load(open(data, "rb"))
stocks = [{"symbol": s["symbol"], "d": S.prepare(s["df"])} for s in raw if s["df"] is not None and len(s["df"]) >= 200]
regime = S.regime_series(cache)
dates = sorted({dt for s in stocks for dt in s["d"].index})
cut = dates[int(len(dates) * 0.7)]
rng = np.random.default_rng(11)
res = {}
for gate in ("非空頭",):
    for exit_mode, hold, tp in (("fixed", 10, 2.0), ("fixed", 20, 3.0), ("fixed", 20, 2.0), ("live", 20, 2.0)):
        for kind in ("breakout", "random"):
            trades = []
            for s in stocks:
                d = s["d"]
                reg = regime.reindex(d.index, method="ffill")
                base = d["quality"] & (reg != "bear")
                if kind == "breakout":
                    sig = base & (d["score"] >= 6)
                else:
                    p = float(((d["score"] >= 6) & base).mean())  # 與突破訊號同頻率
                    sig = base & pd.Series(rng.random(len(d)) < p, index=d.index)
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
            res[f"{exit_mode}-{hold}-{tp}-{kind}"] = {"IS": S.stats(t[t.date < cut]), "OOS": S.stats(t[t.date >= cut])}
            print(exit_mode, hold, tp, kind, res[f"{exit_mode}-{hold}-{tp}-{kind}"], flush=True)
oos_bear = regime[regime.index >= cut].value_counts(normalize=True).round(2).to_dict()
is_bear = regime[(regime.index < cut) & (regime.index >= dates[0])].value_counts(normalize=True).round(2).to_dict()
res["regime_share"] = {"IS": is_bear, "OOS": oos_bear}
print("regime IS", is_bear, "OOS", oos_bear)
json.dump(res, open(out, "w"), ensure_ascii=False, default=str)
