"""
從 TWSE OpenAPI 抓全台股清單（上市 + ETF）

來源：
  - 上市每日成交資訊：https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL
    回傳所有當日有交易的上市證券（含 ETF / 普通股 / TDR / 特別股）
"""
import logging
import time

import requests

log = logging.getLogger(__name__)

TWSE_STOCK_DAY_ALL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
# 備援：傳統 rwd 端點（不同主機/路徑），回 {stat, fields, data(positional)}
TWSE_STOCK_DAY_ALL_LEGACY = (
    "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY_ALL?response=json"
)
_HEADERS = {"User-Agent": "Mozilla/5.0 (TWStockScanner)"}


def _http_get_json(url, timeout=20, retries=3, sleep=1.5):
    """帶重試的 JSON 取得；空回應/非 JSON 視為失敗並重試。"""
    last_err = None
    for i in range(retries):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=timeout)
            r.raise_for_status()
            if not r.text or not r.text.strip():
                raise ValueError("空回應")
            return r.json()
        except Exception as e:
            last_err = e
            log.warning("取清單失敗（第 %d/%d 次）：%s", i + 1, retries, e)
            if i < retries - 1:
                time.sleep(sleep)
    raise last_err


def _fetch_universe_rows():
    """回傳 list[{'Code','Name'}]，先試 OpenAPI，失敗改用傳統端點。"""
    try:
        data = _http_get_json(TWSE_STOCK_DAY_ALL)
        if isinstance(data, list) and data:
            return [{"Code": r.get("Code"), "Name": r.get("Name")} for r in data]
        raise ValueError("OpenAPI 回傳空清單")
    except Exception as e:
        log.warning("OpenAPI 清單失敗，改用備援端點：%s", e)

    data = _http_get_json(TWSE_STOCK_DAY_ALL_LEGACY)
    rows = data.get("data", []) if isinstance(data, dict) else []
    out = []
    for row in rows:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            out.append({"Code": str(row[0]).strip(), "Name": str(row[1]).strip()})
    if not out:
        raise RuntimeError("TWSE 清單兩個端點都取不到資料（稍後再試）")
    return out


def _classify(code, name):
    """
    回傳 (kind, keep)
      kind: 'common' / 'etf' / 'tdr' / 'special' / 'unknown'
      keep: bool
    """
    code = str(code).strip()
    name = str(name).strip()

    # ETF 含字母後綴（債券/槓桿/反向）：00679B, 00687B, 00633L, 00664R...
    # 規則：00 開頭 + 數字 + 單字母結尾，長度 5~7
    if (5 <= len(code) <= 7
            and code.startswith("00")
            and code[-1].isalpha()
            and code[:-1].isdigit()):
        return "etf", True

    # ETF 純數字：0050、00878、009805 等
    if code.isdigit() and code.startswith("00") and 4 <= len(code) <= 6:
        return "etf", True
    if code.isdigit() and len(code) >= 5 and code.startswith("0"):
        return "etf", True

    # 含字母（特別股、權證等）— 上面 ETF 字母規則已先處理
    if not code.isdigit():
        return "special", False

    # TDR：9 開頭 4 碼（91xx、92xx、93xx）
    if len(code) == 4 and code.startswith("9"):
        return "tdr", False

    # 特別股名稱常見「特」、「甲特」、「乙特」
    if "特" in name:
        return "special", False

    # 受益證券、不動產
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
    log.info("從 TWSE 抓取股票清單 ...")
    data = _fetch_universe_rows()

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
