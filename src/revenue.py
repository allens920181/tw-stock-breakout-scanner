# -*- coding: utf-8 -*-
"""
月營收動能（基本面催化劑）

來源：TWSE 上市公司每月營業收入彙總表 t187ap05_L（官方免費、免 key）。
回傳每檔最新月營收的 年增(YoY) / 月增(MoM) / 累計年增，當「動能是否有基本面支撐」的快照確認。

定位（與 chips/margin/earnings 相同）：當日 best-effort 快照，非可回測 alpha。
用途：補上系統唯一缺的「為什麼強」維度——
  - 強勢突破 + 營收年增 → 技術面有基本面背書（加分/評級理由）
  - 純技術噴出 + 營收衰退 → 反指標（可把進場降為觀察）
僅上市；查無者回 None，不參與判斷。
"""
import logging

import requests

from . import cache as cache_mod

log = logging.getLogger(__name__)

_TIMEOUT = 20
_HEADERS = {"User-Agent": "Mozilla/5.0 (stock-scan)"}
_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"


def _to_float(x):
    try:
        return float(str(x).replace(",", "").strip())
    except Exception:
        return None


def fetch_revenue(cache_dir, verify=True, use_cache=True):
    """回傳 { code(無後綴): {yoy_pct, mom_pct, accum_yoy_pct, month} }。"""
    if use_cache:
        cached = cache_mod.load_obj(cache_dir, "revenue_all")
        if cached is not None:
            return cached

    out = {}
    try:
        data = requests.get(_URL, headers=_HEADERS, timeout=_TIMEOUT, verify=verify).json()
    except Exception as e:
        log.warning("TWSE 月營收抓取失敗：%s", e)
        return out

    for row in data:
        try:
            code = str(row.get("公司代號", "")).strip()
            if not code:
                continue
            yoy = _to_float(row.get("營業收入-去年同月增減(%)"))
            mom = _to_float(row.get("營業收入-上月比較增減(%)"))
            accum_yoy = _to_float(row.get("累計營業收入-前期比較增減(%)"))
            month = str(row.get("資料年月", "")).strip() or None
            if yoy is None and mom is None:
                continue
            out[code] = {
                "yoy_pct": yoy, "mom_pct": mom,
                "accum_yoy_pct": accum_yoy, "month": month,
            }
        except Exception:
            continue

    log.info("月營收 %d 檔", len(out))
    if out:
        cache_mod.save_obj(cache_dir, "revenue_all", out)
    return out


def classify_revenue(rev, cfg_rev):
    """
    把營收快照轉成 (confirm_label, warn, is_strong, is_weak)。
    confirm_label: 顯示用；warn: 紅旗文字（衰退）；is_strong/is_weak: 供評級/降級。
    rev=None 或無 yoy → ("—", None, False, False)。
    """
    if not rev or rev.get("yoy_pct") is None:
        return "—", None, False, False
    yoy = rev["yoy_pct"]
    strong = yoy >= cfg_rev.get("yoy_strong", 10.0)
    weak = yoy <= cfg_rev.get("yoy_weak", -20.0)
    if strong:
        return f"營收年增+{yoy:.0f}%", None, True, False
    if weak:
        return f"營收年減{abs(yoy):.0f}%", f"營收年減{abs(yoy):.0f}%", False, True
    return f"營收YoY{yoy:+.0f}%", None, False, False
