"""訊號標籤的顯示規則（操作建議樣式、換手率分級）。"""

import pandas as pd


def action_class(action):
    s = str(action)
    if "進場" in s or "埋伏" in s:
        return "go"
    if "觀察" in s:
        return "watch"
    return "skip"


def turnover_label(val):
    if val is None or pd.isna(val):
        return ""
    v = float(val)
    if v < 3:
        return "偏冷"
    if v < 5:
        return "正常"
    if v < 10:
        return "活絡"
    return "過熱"
