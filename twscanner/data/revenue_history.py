"""
個股月營收歷史（算「營收驚喜」用）。來源：FinMind 公開 API（資料為公開資訊觀測站申報值，免 key、有流量限制）。

和 revenue.py（證交所彙總表，只有最新一個月）不同，這裡逐檔抓近 3 年，所以只對需要的股票抓，
並整批存當日快取。抓不到的股票不回傳，由上層標示「資料不足」。
"""
import datetime as dt
import logging

import requests

from twscanner.core import cache as cache_mod
from twscanner.core.tz import today_tw

log = logging.getLogger(__name__)

_URL = "https://api.finmindtrade.com/api/v4/data"
_TIMEOUT = (6, 20)
_HEADERS = {"User-Agent": "Mozilla/5.0 (stock-scan)"}
_KEY = "revenue_history_v1"


def parse_rows(rows):
    """FinMind 列 → [(營收月份 'YYYY-MM', 營收)]，由舊到新。"""
    out = {}
    for r in rows or []:
        try:
            out[f"{int(r['revenue_year']):04d}-{int(r['revenue_month']):02d}"] = float(r["revenue"])
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(out.items())


def fetch_one(code, start=None):
    start = start or (today_tw() - dt.timedelta(days=365 * 3 + 60)).isoformat()
    r = requests.get(_URL, headers=_HEADERS, timeout=_TIMEOUT,
                     params={"dataset": "TaiwanStockMonthRevenue", "data_id": code, "start_date": start})
    js = r.json()
    if js.get("status") != 200:
        raise RuntimeError(js.get("msg") or f"status {js.get('status')}")
    return parse_rows(js.get("data"))


def fetch_many(codes, cache_dir, progress_cb=None, fetch=fetch_one):
    """回 {代號: [(月份, 營收)]}。當日已抓過的不重抓；連續失敗 5 檔就停（多半是流量上限），已抓到的照樣回傳。"""
    cached = cache_mod.load_obj(cache_dir, _KEY) or {}
    todo = [c for c in dict.fromkeys(codes) if c not in cached]
    fails = 0
    for k, code in enumerate(todo):
        try:
            cached[code] = fetch(code)
            fails = 0
        except Exception as e:
            fails += 1
            log.warning("月營收歷史抓取失敗 %s：%s", code, e)
            if fails >= 5:
                break
        if progress_cb:
            progress_cb((k + 1) / len(todo), f"月營收歷史 {k + 1}/{len(todo)}")
    if todo:
        cache_mod.ensure_dir(cache_dir)
        cache_mod.save_obj(cache_dir, _KEY, cached)
    return {c: cached[c] for c in codes if c in cached}
