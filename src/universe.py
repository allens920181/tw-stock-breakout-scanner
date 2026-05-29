"""
從 TWSE OpenAPI 抓全台股清單（上市 + ETF）

來源：
  - 上市每日成交資訊：https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL
    回傳所有當日有交易的上市證券（含 ETF / 普通股 / TDR / 特別股）
"""
import logging

import requests

log = logging.getLogger(__name__)

TWSE_STOCK_DAY_ALL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"


def _http_get_json(url, timeout=20):
    r = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (TWStockScanner)"},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def _classify(code, name):
    """
    回傳 (kind, keep)
      kind: 'common' / 'etf' / 'tdr' / 'special' / 'unknown'
      keep: bool
    """
    code = str(code).strip()
    name = str(name).strip()

    # 含字母（特別股、權證等）
    if not code.isdigit():
        return "special", False

    # ETF：0 開頭，長度 4~6（0050、00878、009805...）
    if code.startswith("00") or (len(code) >= 5 and code.startswith("0")):
        return "etf", True

    # TDR：9 開頭 4 碼（91xx、92xx、93xx）
    if len(code) == 4 and code.startswith("9"):
        return "tdr", False

    # 特別股名稱常見「特」、「甲特」、「乙特」
    if "特" in name:
        return "special", False

    # 受益證券、不動產（K 開頭也常為 REITs）
    if "受益" in name or "不動產" in name:
        return "special", False

    # 普通股：4 碼純數字、非 0 開頭、非 9 開頭
    if len(code) == 4:
        return "common", True

    return "unknown", False


def fetch_twse_universe(include_common=True, include_etf=True):
    """
    回傳 list[{code, company_name, kind}]
    """
    log.info("從 TWSE OpenAPI 抓取股票清單 ...")
    try:
        data = _http_get_json(TWSE_STOCK_DAY_ALL)
    except Exception as e:
        log.error("TWSE OpenAPI 失敗：%s", e)
        raise

    if not isinstance(data, list):
        raise RuntimeError("TWSE OpenAPI 回傳格式異常")

    out = []
    stats = {"common": 0, "etf": 0, "tdr": 0, "special": 0, "unknown": 0}
    for row in data:
        code = row.get("Code") or row.get("證券代號")
        name = row.get("Name") or row.get("證券名稱")
        if not code or not name:
            continue

        kind, keep = _classify(code, name)
        stats[kind] = stats.get(kind, 0) + 1

        if not keep:
            continue
        if kind == "common" and not include_common:
            continue
        if kind == "etf" and not include_etf:
            continue

        out.append({
            "code": str(code).strip(),
            "company_name": str(name).strip(),
            "kind": kind,
        })

    log.info(
        "TWSE 分類統計：普通股 %d / ETF %d / TDR %d / 特別股 %d / 其他 %d → 採用 %d",
        stats["common"], stats["etf"], stats["tdr"], stats["special"], stats["unknown"],
        len(out),
    )
    return out
