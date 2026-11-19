# -*- coding: utf-8 -*-
"""
產業別對照（族群同步用）

來源：TWSE 上市公司基本資料 t187ap03_L（每檔「產業別」代碼，官方免費、免 key）。
分組以「產業代碼」為準（永遠正確）；名稱為 best-effort 顯示，未列代碼回退「產業<代碼>」。
僅上市；清單中查無產業者回 None，不參與分組（不假裝同族群）。
"""
import logging

import requests

from twscanner.core import cache as cache_mod

log = logging.getLogger(__name__)

_TIMEOUT = 20
_HEADERS = {"User-Agent": "Mozilla/5.0 (stock-scan)"}

# 標準上市產業別代碼 → 名稱
_INDUSTRY = {
    "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維",
    "05": "電機機械", "06": "電器電纜", "08": "玻璃陶瓷", "09": "造紙工業",
    "10": "鋼鐵工業", "11": "橡膠工業", "12": "汽車工業", "14": "建材營造",
    "15": "航運業", "16": "觀光餐旅", "17": "金融保險", "18": "貿易百貨",
    "20": "其他", "21": "化學工業", "22": "生技醫療", "23": "油電燃氣",
    "24": "半導體", "25": "電腦及週邊", "26": "光電業", "27": "通信網路",
    "28": "電子零組件", "29": "電子通路", "30": "資訊服務", "31": "其他電子",
    "32": "文化創意", "33": "農業科技", "34": "電子商務", "35": "綠能環保",
    "36": "數位雲端", "37": "運動休閒", "38": "居家生活", "91": "其他",
}


def _name(code):
    code = str(code).strip()
    return _INDUSTRY.get(code, f"產業{code}") if code else None


def fetch_sectors(cache_dir, verify=True, use_cache=True):
    """回傳 { code(無後綴): 產業名稱 }（僅上市；上櫃不在內 → 視為未知）。"""
    if use_cache:
        cached = cache_mod.load_obj(cache_dir, "sectors_all")
        if cached is not None:
            return cached

    out = {}
    url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    try:
        data = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, verify=verify).json()
    except Exception as e:
        log.warning("TWSE 產業別抓取失敗：%s", e)
        return out
    for row in data:
        try:
            code = str(row.get("公司代號", "")).strip()
            ind = _name(row.get("產業別", ""))
            if code and ind:
                out[code] = ind
        except Exception:
            continue
    log.info("產業別 %d 檔", len(out))
    if out:
        cache_mod.save_obj(cache_dir, "sectors_all", out)
    return out


def _to_float(x):
    try:
        return float(str(x).replace(",", "").strip())
    except Exception:
        return None


def fetch_shares_official(cache_dir, verify=True, use_cache=True):
    """
    回傳 { code(無後綴): 已發行普通股數 }，來源 TWSE 上市公司基本資料 t187ap03_L。
    優先用「已發行普通股數或TDR原發行股數」欄位；缺值則用 實收資本額 / 每股面額 推估。
    官方免費、免 key，且不被資料中心 IP 阻擋（解決雲端 Yahoo 股數抓不到 → 換手率空白）。
    僅上市；查無者回傳不含該 code（交由 yfinance 補）。
    """
    if use_cache:
        cached = cache_mod.load_obj(cache_dir, "shares_official")
        if cached is not None:
            return cached

    out = {}
    url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    try:
        data = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, verify=verify).json()
    except Exception as e:
        log.warning("TWSE 流通股數抓取失敗：%s", e)
        return out

    for row in data:
        try:
            code = str(row.get("公司代號", "")).strip()
            if not code:
                continue
            shares = _to_float(row.get("已發行普通股數或TDR原發行股數"))
            if not shares or shares <= 0:
                cap = _to_float(row.get("實收資本額"))
                par = _to_float(row.get("普通股每股面額")) or 10.0
                if cap and par > 0:
                    shares = cap / par
            if shares and shares > 0:
                out[code] = shares
        except Exception:
            continue

    log.info("官方流通股數 %d 檔", len(out))
    if out:
        cache_mod.save_obj(cache_dir, "shares_official", out)
    return out
