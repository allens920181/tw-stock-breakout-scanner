"""
融資券：融資增減 + 券資比（官方免費 API，免 API key）

來源（最新交易日，單筆即含前日 + 今日餘額，免多日抓取）：
  上市 TWSE：https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN（positional）
（僅上市；上櫃不納入。）

回傳以「股票代號（無後綴）」為 key：
  { code: {
      "margin_bal_lots": int,    # 融資今日餘額（張）
      "margin_chg_pct":  float,  # 融資餘額單日增減 %（散戶槓桿變化）
      "short_bal_lots":  int,    # 融券今日餘額（張）
      "short_margin_ratio": float# 券資比 % = 融券 / 融資 × 100
  } }

用途：
  融資爆增 = 散戶追高槓桿（反指標，過熱警示）
  券資比偏高 = 潛在軋空題材（中性偏多參考）
失敗 → 回空 dict，評分端優雅降級。
"""
import logging
from datetime import timedelta

from .tz import today_tw

import requests

from . import cache as cache_mod

log = logging.getLogger(__name__)

_TIMEOUT = 20
_HEADERS = {"User-Agent": "Mozilla/5.0 (stock-scan)",
            "Referer": "https://www.tpex.org.tw/"}


def _to_int(s):
    try:
        return int(str(s).replace(",", "").replace(" ", "").strip())
    except Exception:
        return 0


def _chg_pct(today, prev):
    if prev and prev > 0:
        return round((today - prev) / prev * 100, 2)
    return None


def _ratio(short_bal, margin_bal):
    if margin_bal and margin_bal > 0:
        return round(short_bal / margin_bal * 100, 2)
    return None


def _twse(verify=True):
    """上市融資券：往回找最近交易日（positional）。"""
    out = {}
    for off in range(0, 8):
        d = (today_tw() - timedelta(days=off)).strftime("%Y%m%d")
        url = (f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
               f"?date={d}&selectType=ALL&response=json")
        try:
            js = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, verify=verify).json()
        except Exception as e:
            log.warning("TWSE MI_MARGN %s 失敗：%s", d, e)
            continue
        if js.get("stat") != "OK":
            continue
        rows = []
        for t in js.get("tables", []):
            data = t.get("data", [])
            if data and len(data[0]) >= 16:   # 個股表（16 欄）
                rows = data
                break
        if not rows:
            continue
        for r in rows:
            try:
                code = str(r[0]).strip()
                if not code or not code[0].isdigit():
                    continue
                margin_prev = _to_int(r[5])
                margin_today = _to_int(r[6])
                short_today = _to_int(r[12])
                out[code] = {
                    "margin_bal_lots": margin_today,
                    "margin_chg_pct": _chg_pct(margin_today, margin_prev),
                    "short_bal_lots": short_today,
                    "short_margin_ratio": _ratio(short_today, margin_today),
                }
            except Exception:
                continue
        break
    log.info("TWSE 融資券 %d 檔", len(out))
    return out


def fetch_margin(cache_dir, verify=True, use_cache=True):
    """回傳 { code: {...} }（僅上市）；當日快取；失敗回空 dict。"""
    if use_cache:
        cached = cache_mod.load_obj(cache_dir, "margin_all")
        if cached is not None:
            return cached

    merged = {}
    try:
        merged.update(_twse(verify=verify))
    except Exception as e:
        log.warning("TWSE 融資券整體失敗：%s", e)

    if merged:
        cache_mod.save_obj(cache_dir, "margin_all", merged)
    return merged
