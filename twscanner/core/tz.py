# -*- coding: utf-8 -*-
"""
台灣時區工具（Asia/Taipei = UTC+8，無日光節約）。

雲端伺服器多跑在 UTC，直接用 datetime.now()/date.today() 會慢 8 小時、
半夜還會差一天 → 掃描時間、日誌日期、期交所/TWSE 抓取日期全偏。
全專案的「現在/今天」一律改用這裡。
"""
from datetime import datetime, timedelta, timezone

TW_TZ = timezone(timedelta(hours=8))


def now_tw():
    """台灣當下時間（tz-aware）。"""
    return datetime.now(TW_TZ)


def today_tw():
    """台灣當下日期。"""
    return now_tw().date()
