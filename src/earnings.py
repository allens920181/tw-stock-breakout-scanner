# -*- coding: utf-8 -*-
"""
財報避雷：抓下一個財報日，進場前後 blackout。

來源：yfinance Ticker.calendar['Earnings Date']（best-effort）。
台股財報日 yfinance 偶有缺漏 → 抓不到就回 None、不做 blackout（不影響其他評分）。
逐檔並行抓取並快取一天（與抓股數同模式）。
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import yfinance as yf

from . import cache as cache_mod

log = logging.getLogger(__name__)


def _next_earnings_one(symbol):
    key = f"earn_{symbol.replace('.', '_')}"
    try:
        t = yf.Ticker(symbol)
        cal = t.calendar
        ed = None
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
        if isinstance(ed, (list, tuple)) and ed:
            ed = ed[0]
        # 統一成 ISO 字串（cache 友善）
        if hasattr(ed, "isoformat"):
            return symbol, ed.isoformat()[:10]
    except Exception:
        pass
    return symbol, None


def fetch_all_earnings(symbols, cache_dir, max_workers, use_cache=True):
    """回傳 { symbol: 'YYYY-MM-DD' or None }，當日快取。"""
    out = {}
    pending = []
    if use_cache:
        for s in symbols:
            c = cache_mod.load_obj(cache_dir, f"earn_{s.replace('.', '_')}")
            if c is not None:
                out[s] = c.get("v") if isinstance(c, dict) else c
            else:
                pending.append(s)
    else:
        pending = list(symbols)

    if pending:
        log.info("平行抓財報日 %d 檔 (%d 緒)", len(pending), max_workers)
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(_next_earnings_one, s) for s in pending]
            for fu in as_completed(futures):
                try:
                    sym, val = fu.result()
                    out[sym] = val
                    cache_mod.save_obj(cache_dir, f"earn_{sym.replace('.', '_')}", {"v": val})
                except Exception as e:
                    log.warning("抓財報日失敗：%s", e)
    return out


def days_to_earnings(earnings_iso, today=None):
    """回傳距財報日天數（正=未到、負=已過）；無法解析回 None。"""
    if not earnings_iso:
        return None
    try:
        y, m, d = (int(x) for x in str(earnings_iso)[:10].split("-"))
        ed = date(y, m, d)
        ref = today or date.today()
        return (ed - ref).days
    except Exception:
        return None
