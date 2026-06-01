"""
籌碼面：三大法人 / 外資買賣超 + 連買天數（官方免費 API，免 API key）

來源（可帶日期，用於計算連買天數）：
  上市 TWSE：https://www.twse.com.tw/rwd/zh/fund/T86
（僅上市；上櫃不納入。）

回傳以「股票代號（無 .TW 後綴）」為 key 的 dict：
  { code: {
      "inst_net_lots":   int,   # 最新交易日 三大法人合計買賣超（張）
      "foreign_net_lots":int,   # 最新交易日 外資買賣超（張）
      "inst_buy_streak": int,   # 三大法人「連續買超」天數（最新日往回算）
      "inst_net_5d_lots":int,   # 近 N 日三大法人累計買賣超（張）
      "date": "YYYYMMDD",
  } }
單位一律換算成「張」（股數 / 1000，四捨五入）。

設計：每市場每交易日各 1 次請求（非逐檔），整體結果快取一天。
失敗（假日 / 無網路 / 改版）→ 該日略過；全失敗回空 dict，評分端優雅降級。
"""
import logging
from datetime import date, timedelta

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


def _lots(shares):
    return int(round(shares / 1000.0))


def _twse_day(d, verify=True):
    """單一交易日 上市三大法人。回傳 (ok, {code: (inst_lots, foreign_lots)})。"""
    url = (f"https://www.twse.com.tw/rwd/zh/fund/T86"
           f"?date={d}&selectType=ALL&response=json")
    try:
        js = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, verify=verify).json()
    except Exception as e:
        log.warning("TWSE T86 %s 失敗：%s", d, e)
        return False, {}
    if js.get("stat") != "OK" or not js.get("data"):
        return False, {}
    out = {}
    for row in js["data"]:
        try:
            code = str(row[0]).strip()
            if not code or not code[0].isdigit():
                continue
            out[code] = (_lots(_to_int(row[-1])), _lots(_to_int(row[4])))
        except Exception:
            continue
    return True, out


def _build(history):
    """history: list[ {code: (inst, foreign)} ]，[0] 為最新日。計算連買 / 累計。"""
    if not history:
        return {}
    codes = set()
    for day in history:
        codes.update(day.keys())

    result = {}
    for code in codes:
        series = [day.get(code) for day in history]   # 最新→最舊，可能含 None
        latest = series[0]
        if latest is None:
            # 最新日無此檔（可能停牌）→ 用第一個有值日當 latest
            latest = next((s for s in series if s is not None), (0, 0))
        inst_latest, foreign_latest = latest

        # 連買天數：最新日往回，inst > 0 連續計數
        streak = 0
        for s in series:
            if s is not None and s[0] > 0:
                streak += 1
            else:
                break

        net_sum = sum(s[0] for s in series if s is not None)

        result[code] = {
            "inst_net_lots": inst_latest,
            "foreign_net_lots": foreign_latest,
            "inst_buy_streak": streak,
            "inst_net_5d_lots": net_sum,
            "date": None,
        }
    return result


def fetch_chips(cache_dir, days=5, verify=True, use_cache=True):
    """
    抓近 `days` 個交易日的三大法人/外資買賣超，計算連買天數與累計。
    當日快取；失敗回空 dict。
    """
    if use_cache:
        cached = cache_mod.load_obj(cache_dir, "chips_all")
        if cached is not None:
            return cached

    history = []        # list[{code: (inst, foreign)}]，最新→最舊
    latest_date = None
    off = 0
    # 從今天往回找交易日（以 TWSE 是否有資料為交易日判準）
    while len(history) < days and off < days + 10:
        d = (date.today() - timedelta(days=off)).strftime("%Y%m%d")
        off += 1
        try:
            ok, tw = _twse_day(d, verify=verify)
        except Exception as e:
            log.warning("TWSE %s 整體失敗：%s", d, e)
            ok, tw = False, {}
        if not ok:
            continue
        history.append(tw)
        if latest_date is None:
            latest_date = d

    result = _build(history)
    for v in result.values():
        v["date"] = latest_date
    log.info("籌碼：%d 檔 / %d 交易日（最新 %s）",
             len(result), len(history), latest_date)

    if result:
        cache_mod.save_obj(cache_dir, "chips_all", result)
    return result
