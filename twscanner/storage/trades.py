"""
已實現交易紀錄的持久化：只存在「登入後的雲端空間」（Neon tw_kv）。

刻意不寫伺服器本機檔案：部署在 Streamlit Cloud 時所有訪客共用同一台機器，
本機檔案會讓任何人都看得到你的交易。未登入時紀錄只留在瀏覽器 session，請用匯出 / 匯入備份
（與持股的作法一致）。
"""
from twscanner.storage import cloud

_KEY = "trades"


def load_records(owner=None):
    if owner and cloud.is_enabled():
        recs = cloud.kv_get(owner, _KEY)
        if recs is not None:
            return list(recs)
    return []


def save_records(records, owner=None):
    """有登入才寫雲端；回傳是否已永久保存。"""
    if owner and cloud.is_enabled():
        return bool(cloud.kv_set(owner, _KEY, records))
    return False
