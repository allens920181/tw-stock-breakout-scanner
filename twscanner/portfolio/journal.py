# -*- coding: utf-8 -*-
"""
前向訊號日誌（live OOS）

把每次掃描的「進場」清單存檔，事後用真實後續價格量「實際 R」——
這是回測（歷史模擬）之外，唯一誠實的「實戰準不準」驗證。

流程：
  掃描 → log_signals() 追加當日進場清單（依日期+代號去重）
  之後 → evaluate_journal() 用後續 OHLC 模擬出場，算 realized R / 狀態
       → summarize_journal() 給勝率 / 期望值 / 樣本數（依評級、模式分組）

出場模擬（與回測一致、保守）：進場後逐日，先碰停損記 −1R、先碰 +2R 記 +2R；
未出場 = 進行中，以最新收盤計未實現 R。風險基準 = 進場價 − 停損（毛值）。
"""
import json
import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

JOURNAL_PATH = Path.home() / ".tw_scanner_journal.json"

_FIELDS = [
    "掃描日", "股票", "公司名稱", "模式", "訊號判斷", "綜合評級",
    "進場參考價", "停損價", "目標價1(+1R半倉)", "目標價2(+2R出清)",
    "評分", "相對強度RS%",
]


def load_journal(path=None):
    p = Path(path) if path else JOURNAL_PATH
    if not p.exists():
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_journal(records, path=None):
    p = Path(path) if path else JOURNAL_PATH
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=1)
        return True
    except Exception as e:
        log.warning("日誌儲存失敗：%s", e)
        return False


def log_signals(df, scan_date, mode="breakout", signals=("進場",), path=None):
    """把掃描結果中的進場（預設）清單追加進日誌。回傳新增筆數。"""
    if df is None or len(df) == 0 or "訊號判斷" not in df.columns:
        return 0
    records = load_journal(path)
    existing = {(r.get("掃描日"), r.get("股票")) for r in records}
    added = 0
    for _, row in df.iterrows():
        if row.get("訊號判斷") not in signals:
            continue
        sym = row.get("股票")
        key = (scan_date, sym)
        if key in existing:
            continue
        rec = {"掃描日": scan_date, "模式": mode}
        for col in _FIELDS:
            if col in ("掃描日", "模式"):
                continue
            v = row.get(col)
            if isinstance(v, (pd.Timestamp,)):
                v = str(v)
            rec[col] = (None if (isinstance(v, float) and pd.isna(v)) else v)
        records.append(rec)
        existing.add(key)
        added += 1
    if added:
        save_journal(records, path)
    return added


def _entry_stop_risk(rec):
    entry = rec.get("進場參考價")
    stop = rec.get("停損價")
    try:
        entry = float(entry); stop = float(stop)
    except (TypeError, ValueError):
        return None, None, None
    risk = entry - stop
    return entry, stop, (risk if risk > 0 else None)


def evaluate_record(rec, df):
    """用進場日之後的 OHLC 模擬出場，回 outcome dict。"""
    entry, stop, risk = _entry_stop_risk(rec)
    out = {"狀態": "—", "實際R": None, "持有天數": None,
           "最佳R": None, "最差R": None, "出場日": None}
    if entry is None or risk is None or df is None or df.empty:
        out["狀態"] = "無法評估"
        return out

    t2 = rec.get("目標價2(+2R出清)")
    try:
        t2 = float(t2)
    except (TypeError, ValueError):
        t2 = entry + 2 * risk

    sd = rec.get("掃描日")
    try:
        after = df[df.index.date > pd.to_datetime(sd).date()]
    except Exception:
        after = df
    if after is None or after.empty:
        out["狀態"] = "進行中（無後續資料）"
        return out

    max_r, min_r = None, None
    for i in range(len(after)):
        bar = after.iloc[i]
        hi, lo, cl = float(bar["High"]), float(bar["Low"]), float(bar["Close"])
        r_hi = (hi - entry) / risk
        r_lo = (lo - entry) / risk
        max_r = r_hi if max_r is None else max(max_r, r_hi)
        min_r = r_lo if min_r is None else min(min_r, r_lo)
        # 保守：同日先假設碰停損
        if lo <= stop:
            out.update({"狀態": "停損", "實際R": -1.0, "持有天數": i + 1,
                        "出場日": str(after.index[i].date()),
                        "最佳R": round(max_r, 2), "最差R": round(min_r, 2)})
            return out
        if hi >= t2:
            out.update({"狀態": "達標+2R", "實際R": 2.0, "持有天數": i + 1,
                        "出場日": str(after.index[i].date()),
                        "最佳R": round(max_r, 2), "最差R": round(min_r, 2)})
            return out
    # 未出場：進行中
    last_close = float(after.iloc[-1]["Close"])
    out.update({"狀態": "進行中", "實際R": round((last_close - entry) / risk, 2),
                "持有天數": len(after),
                "最佳R": round(max_r, 2) if max_r is not None else None,
                "最差R": round(min_r, 2) if min_r is not None else None})
    return out


def evaluate_journal(records, df_map):
    """df_map: {symbol: OHLC df}。回傳每筆 rec 併入 outcome 的 list。"""
    rows = []
    for rec in records:
        df = df_map.get(rec.get("股票"))
        outcome = evaluate_record(rec, df)
        merged = dict(rec)
        merged.update(outcome)
        rows.append(merged)
    return rows


def summarize_journal(evaluated):
    """彙整 live OOS 績效：已結案勝率/期望值 + 進行中數。"""
    closed = [r for r in evaluated if r.get("狀態") in ("停損", "達標+2R")]
    openg = [r for r in evaluated if r.get("狀態") == "進行中"]
    n_closed = len(closed)
    wins = [r for r in closed if (r.get("實際R") or 0) > 0]
    rs = [r["實際R"] for r in closed if r.get("實際R") is not None]
    expectancy = sum(rs) / len(rs) if rs else None
    open_rs = [r["實際R"] for r in openg if r.get("實際R") is not None]
    return {
        "總訊號數": len(evaluated),
        "已結案": n_closed,
        "進行中": len(openg),
        "勝率%": round(len(wins) / n_closed * 100, 1) if n_closed else None,
        "已結案期望值R": round(expectancy, 3) if expectancy is not None else None,
        "進行中平均未實現R": round(sum(open_rs) / len(open_rs), 2) if open_rs else None,
    }
