"""股票代號 → 名稱查詢，含 yfinance 後備與本地持久化快取"""
import json
import logging
from pathlib import Path

import yfinance as yf

log = logging.getLogger(__name__)

CACHE_FILE = Path(".cache") / "name_lookup.json"


def _load_cache():
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(data):
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning("name_lookup 寫入快取失敗：%s", e)


def lookup_via_yf(code):
    """以 yfinance 嘗試查詢名稱（.TW → .TWO）"""
    for suffix in (".TW", ".TWO"):
        sym = f"{code}{suffix}"
        try:
            info = yf.Ticker(sym).info
            name = info.get("shortName") or info.get("longName")
            if name:
                return str(name).strip()
        except Exception:
            continue
    return None


def lookup_names(codes, twse_map):
    """
    對一組代號回傳 {code: name}，順序：
      1. twse_map（已有的 OpenAPI 對照）
      2. 本地 cache file
      3. yfinance fallback（並寫入 cache）

    回傳的 dict 只包含找到的；找不到的 code 不會在 dict 內。
    """
    cache = _load_cache()
    out = {}
    new_in_cache = False

    for code in codes:
        if not code:
            continue

        # 1. TWSE map
        if code in twse_map:
            out[code] = twse_map[code]
            continue

        # 2. 本地快取
        if code in cache:
            if cache[code]:
                out[code] = cache[code]
            continue

        # 3. yfinance fallback
        name = lookup_via_yf(code)
        cache[code] = name or ""  # 即使找不到也記錄，避免重複查
        new_in_cache = True
        if name:
            out[code] = name

    if new_in_cache:
        _save_cache(cache)

    return out
