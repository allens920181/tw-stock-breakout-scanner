"""
投資組合層級回測引擎（研究用）：回答「照規則買一籃子、定期換股，扣成本後有沒有贏過直接持有 0050」。

和 study.py（逐筆交易、以 R 計）不同，這裡模擬的是一個真的帳戶：固定檔數、等權、
現金有限、隔天開盤成交、漲停買不到、跌停鎖死賣不掉、手續費／證交稅／滑價全算。

資料：{symbol: DataFrame(Open/High/Low/Close/Adj Close/Volume)}，只含目前仍上市的股票
（存活者偏差：越早的年份偏差越大，結果偏樂觀，見 README）。
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

FEE = 0.001425            # 手續費（單邊，未折讓）
TAX = 0.003               # 證交稅（賣出）
SLIP = 0.0015             # 滑價（單邊）
BUY_COST = FEE + SLIP
SELL_COST = FEE + TAX + SLIP


@dataclass
class Panel:
    Op: pd.DataFrame       # 開盤（原始）
    H: pd.DataFrame
    L: pd.DataFrame
    C: pd.DataFrame       # 收盤（原始）
    A: pd.DataFrame       # 還原收盤（含息）
    V: pd.DataFrame       # 成交股數
    AO: pd.DataFrame      # 還原開盤


def build_panel(prices: dict, start="2000-01-01", exclude=("^TWII", "0050.TW", "006208.TW")) -> Panel:
    cols = {}
    for name in ("Open", "High", "Low", "Close", "Adj Close", "Volume"):
        x = pd.DataFrame({k: v[name] for k, v in prices.items() if k not in exclude})
        x.index = pd.to_datetime(x.index).tz_localize(None)
        cols[name] = x.sort_index().loc[start:]
    live = (cols["Volume"] > 0) & (cols["Close"] > 0)
    Op, H, L, C, A, V = (cols[k].where(live) for k in ("Open", "High", "Low", "Close", "Adj Close", "Volume"))
    # Yahoo 偶有壞點：單日還原報酬超過漲跌幅限制很多的，視為資料錯誤，把那一天整列設為缺值
    r = A.pct_change(fill_method=None)
    bad = (r.abs() > 0.25)
    for df in (Op, H, L, C, A, V):
        df.mask(bad, inplace=True)
    A = A.ffill(limit=5).where(C.notna() | bad)          # 壞點當天沿用前值，報酬為 0
    C2 = C.ffill(limit=5).where(C.notna() | bad)
    AO = (Op * (A / C2)).where(Op.notna())
    return Panel(Op, H, L, C2, A, V.fillna(0), AO)


def tradable_mask(p: Panel, min_price=10.0, min_lots=500, min_value=0.0) -> pd.DataFrame:
    """可交易：股價 ≥ min_price、20 日均量 ≥ min_lots 張、（可選）20 日均成交值 ≥ min_value 元。"""
    v20 = p.V.rolling(20).mean()
    ok = (p.C >= min_price) & (v20 >= min_lots * 1000)
    if min_value:
        ok &= (p.C * p.V).rolling(20).mean() >= min_value
    return ok & p.C.notna()


@dataclass
class Rules:
    n: int = 20                    # 持股檔數
    step: int = 20                 # 每幾個交易日檢查換股一次
    keep_pct: float = 0.0          # 續抱緩衝：名次仍在前 keep_pct 就不換（0 = 掉出前 n 名就換）
    trail: float = 0.0             # 個股移動停損（從進場後收盤高點回落幾成；0 = 不用）
    stop: float = 0.0              # 個股固定停損（從進場價跌幾成；0 = 不用）
    regime: str = "none"           # none / cash（空頭全出）/ no_new（空頭不買新的）
    min_score: float = -np.inf     # 分數門檻（例如距一年高點 ≥ 0.9）
    offset: int = 0                # 換股日位移（測試「剛好哪一天換」的運氣成分）


def simulate(p: Panel, score: pd.DataFrame, tradable: pd.DataFrame, rules: Rules,
             bear: pd.Series | None = None, start=None, end=None, capital=1_000_000.0, seed=None,
             keep: pd.DataFrame | None = None):
    """回傳 (每日淨值 Series, 交易明細 DataFrame, 統計 dict)。seed 不為 None 時同分隨機排序。

    keep：續抱條件（布林表）。有給的話，持股只要仍可交易且 keep 為真就不換，不看名次。
    """
    dates = p.C.index
    i0 = dates.searchsorted(pd.Timestamp(start)) if start else 260
    i1 = dates.searchsorted(pd.Timestamp(end)) if end else len(dates)
    Op, H, L, C, A, AO = (x.to_numpy() for x in (p.Op, p.H, p.L, p.C, p.A, p.AO))
    S = score.to_numpy(dtype=float)
    T = tradable.to_numpy()
    K = keep.to_numpy() if keep is not None else None
    B = bear.reindex(dates).fillna(False).to_numpy() if bear is not None else np.zeros(len(dates), bool)
    rng = np.random.default_rng(seed) if seed is not None else None

    cash = capital
    pos = {}          # col -> dict(sh, entry_px, entry_i, peak)
    pending_sell, pending_buy = set(), []
    equity, trades = [], []
    last_a = np.zeros(A.shape[1])
    turnover = 0.0

    for i in range(i0, i1):
        a = A[i]
        last_a = np.where(np.isnan(a), last_a, a)
        # --- 開盤：執行昨天收盤決定的單 ---
        for c in list(pending_sell):
            if c not in pos:
                pending_sell.discard(c)
                continue
            if np.isnan(AO[i, c]):
                continue                                             # 停牌：延後
            locked = (H[i, c] == L[i, c]) and (C[i, c] <= C[i - 1, c] * 0.905)
            if locked:
                continue                                             # 跌停鎖死：賣不掉，延後
            px = AO[i, c]
            val = pos[c]["sh"] * px * (1 - SELL_COST)
            cash += val
            turnover += pos[c]["sh"] * px
            trades.append((dates[pos[c]["entry_i"]], dates[i], p.C.columns[c],
                           px * (1 - SELL_COST) / pos[c]["entry_px"] - 1, i - pos[c]["entry_i"]))
            del pos[c]
            pending_sell.discard(c)
        if pending_buy:
            eq_open = cash + sum(v["sh"] * (AO[i, c] if not np.isnan(AO[i, c]) else last_a[c]) for c, v in pos.items())
            slot = eq_open / rules.n
            for c in pending_buy:
                if len(pos) >= rules.n or c in pos:
                    break
                if np.isnan(AO[i, c]) or np.isnan(C[i - 1, c]):
                    continue
                if Op[i, c] >= C[i - 1, c] * 1.095 and H[i, c] == L[i, c]:
                    continue                                         # 一字漲停：買不到
                budget = min(slot, cash)
                if budget < slot * 0.5:
                    break
                px = AO[i, c] * (1 + BUY_COST)
                pos[c] = {"sh": budget / px, "entry_px": px, "entry_i": i, "peak": AO[i, c]}
                cash -= budget
                turnover += budget
            pending_buy = []
        # --- 收盤：估值 ---
        eq = cash + sum(v["sh"] * last_a[c] for c, v in pos.items())
        equity.append(eq)
        # --- 收盤：決定明天的單 ---
        for c, v in pos.items():
            if np.isnan(a[c]):
                continue
            v["peak"] = max(v["peak"], a[c])
            if rules.trail and a[c] <= v["peak"] * (1 - rules.trail):
                pending_sell.add(c)
            if rules.stop and a[c] <= v["entry_px"] * (1 - rules.stop):
                pending_sell.add(c)
        is_bear = bool(B[i])
        if rules.regime == "cash" and is_bear:
            pending_sell.update(pos.keys())
            continue
        empty = not pos and not pending_buy          # 空手（例如空頭全出之後）：不等換股日，隔天就重新建倉
        if (i - i0 + rules.offset) % rules.step != 0 and not empty:
            continue                                  # 非換股日：停損空出的位子等下次換股日再補
        s = S[i].copy()
        ok = T[i] & ~np.isnan(s) & (s >= rules.min_score)
        if rng is not None:
            s = s + rng.random(s.shape) * 1e-9
        s[~ok] = -np.inf
        order = np.argsort(-s)
        n_ok = int(ok.sum())
        rank = np.empty(len(s), int)
        rank[order] = np.arange(len(s))
        keep_rank = max(rules.n, int(n_ok * rules.keep_pct)) if rules.keep_pct else rules.n
        for c in pos:
            if K is not None:
                if not (T[i, c] and K[i, c]):
                    pending_sell.add(c)
            elif not ok[c] or rank[c] >= keep_rank:
                pending_sell.add(c)
        if rules.regime == "no_new" and is_bear:
            continue
        stay = [c for c in pos if c not in pending_sell]
        want = [int(c) for c in order[:n_ok] if c not in pos][: rules.n - len(stay)]
        pending_buy = want

    eq = pd.Series(equity, index=dates[i0:i1])
    tr = pd.DataFrame(trades, columns=["entry", "exit", "symbol", "ret", "days"])
    return eq, tr, {"turnover_per_year": turnover / eq.mean() / (len(eq) / 250) if len(eq) else 0.0}


def perf(eq: pd.Series) -> dict:
    r = eq.pct_change().dropna()
    yrs = len(eq) / 250
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1
    dd = eq / eq.cummax() - 1
    m = eq.resample("ME").last().pct_change().dropna()
    return {"cagr": cagr * 100, "vol": r.std() * np.sqrt(250) * 100,
            "sharpe": r.mean() / r.std() * np.sqrt(250) if r.std() else 0.0,
            "mdd": dd.min() * 100, "month_win": (m > 0).mean() * 100, "worst_month": m.min() * 100}


def compare(eq: pd.Series, bench: pd.Series) -> dict:
    """相對基準：月超額報酬、t 值（Newey-West 3 期）、年度勝率、滾動 3 年勝率。"""
    b = bench.reindex(eq.index).ffill()
    m = pd.DataFrame({"s": eq.resample("ME").last(), "b": b.resample("ME").last()}).pct_change().dropna()
    x = (m["s"] - m["b"]).to_numpy()
    n = len(x)
    mu = x.mean()
    e = x - mu
    var = (e @ e) / n
    for lag in (1, 2, 3):
        var += 2 * (1 - lag / 4) * (e[lag:] @ e[:-lag]) / n
    t = mu / np.sqrt(var / n) if var > 0 else 0.0
    y = pd.DataFrame({"s": eq.resample("YE").last(), "b": b.resample("YE").last()}).pct_change().dropna()
    roll = pd.DataFrame({"s": eq, "b": b}).pct_change(750).dropna()
    return {"excess_month": mu * 100, "t": t, "months": n, "month_beat": (x > 0).mean() * 100,
            "years_beat": int((y["s"] > y["b"]).sum()), "years": int(len(y)),
            "roll3y_beat": (roll["s"] > roll["b"]).mean() * 100 if len(roll) else float("nan"),
            "tracking_error": x.std() * np.sqrt(12) * 100}
