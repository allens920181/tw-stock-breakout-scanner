"""
財報資料（證交所 OpenAPI，官方免費、免 key，僅上市公司）。

只取「最新一次公告」的數字（OpenAPI 不提供歷史），全部是年初累計值：
  - t187ap14_L   各產業 EPS 彙總：營業收入、營業利益、稅後淨利、基本每股盈餘、年度/季別
  - t187ap17_L   營益分析：毛利率、營業利益率、稅前/稅後純益率
  - t187ap07_L_* 資產負債表（一般業 ci、證券 bd、異業 mim、銀行 basi、保險 ins、金控 fh）

回傳 { code: {...} }，欄位缺就不放；抓失敗回空 dict，呼叫端要能處理「沒有財報」。
"""
import logging
import time

import requests

from twscanner.core import cache as cache_mod

log = logging.getLogger(__name__)

_BASE = "https://openapi.twse.com.tw/v1/opendata/"
_TIMEOUT = 25
_HEADERS = {"User-Agent": "Mozilla/5.0 (stock-scan)"}
_BALANCE_SETS = ("ci", "bd", "mim", "basi", "ins", "fh")


def _num(x):
    try:
        s = str(x).replace(",", "").strip()
        return float(s) if s not in ("", "--", "-", "None") else None
    except Exception:
        return None


def _first(row, *keys):
    for k in keys:
        v = _num(row.get(k))
        if v is not None:
            return v
    return None


def _get(endpoint, verify, retries=2):
    """回傳 (rows, ok)。TWSE 偶爾限流回空白 → 退避重試。"""
    for i in range(retries + 1):
        try:
            return requests.get(_BASE + endpoint, headers=_HEADERS, timeout=_TIMEOUT,
                                verify=verify).json(), True
        except Exception as e:
            if i == retries:
                log.warning("財報 %s 抓取失敗：%s", endpoint, e)
            else:
                time.sleep(2 * (i + 1))
    return [], False


def parse_eps(rows):
    out = {}
    for r in rows or []:
        code = str(r.get("公司代號", "")).strip()
        if not code:
            continue
        out[code] = {
            "year": str(r.get("年度", "")).strip(),
            "quarter": str(r.get("季別", "")).strip(),
            "industry": str(r.get("產業別", "")).strip() or None,
            "revenue_k": _num(r.get("營業收入")),          # 仟元
            "op_income_k": _num(r.get("營業利益")),
            "net_income_k": _num(r.get("稅後淨利")),
            "eps": _num(r.get("基本每股盈餘(元)")),
        }
    return out


def parse_ratios(rows):
    out = {}
    for r in rows or []:
        code = str(r.get("公司代號", "")).strip()
        if not code:
            continue
        out[code] = {
            "gross_margin": _num(r.get("毛利率(%)(營業毛利)/(營業收入)")),
            "op_margin": _num(r.get("營業利益率(%)(營業利益)/(營業收入)")),
            "net_margin": _num(r.get("稅後純益率(%)(稅後純益)/(營業收入)")),
        }
    return out


def parse_balance(rows):
    out = {}
    for r in rows or []:
        code = str(r.get("公司代號", "")).strip()
        if not code:
            continue
        rec = {
            "assets_k": _first(r, "資產總計", "資產總額"),
            "liabilities_k": _first(r, "負債總計", "負債總額"),
            "equity_k": _first(r, "權益總計", "權益總額"),
            "current_assets_k": _first(r, "流動資產"),
            "current_liabilities_k": _first(r, "流動負債"),
            "bvps": _first(r, "每股參考淨值"),
        }
        out[code] = {k: v for k, v in rec.items() if v is not None}
    return out


def fetch_fundamentals(cache_dir, verify=True, use_cache=True):
    """{ code: {year, quarter, industry, revenue_k, op_income_k, net_income_k, eps,
                gross_margin, op_margin, net_margin, assets_k, liabilities_k, equity_k,
                current_assets_k, current_liabilities_k, bvps} }"""
    if use_cache:
        c = cache_mod.load_obj(cache_dir, "fundamentals_all")
        if c is not None:
            return c
    merged, complete = {}, True

    def pull(endpoint, parser):
        nonlocal complete
        rows, ok = _get(endpoint, verify)
        complete = complete and ok
        for code, rec in parser(rows).items():
            merged.setdefault(code, {}).update({k: v for k, v in rec.items() if v is not None})

    pull("t187ap14_L", parse_eps)
    pull("t187ap17_L", parse_ratios)
    for kind in _BALANCE_SETS:
        pull(f"t187ap07_L_{kind}", parse_balance)
    log.info("財報 %d 檔", len(merged))
    if merged and complete and use_cache:   # 有任何來源失敗就不快取，下次重抓
        cache_mod.ensure_dir(cache_dir)
        cache_mod.save_obj(cache_dir, "fundamentals_all", merged)
    return merged
