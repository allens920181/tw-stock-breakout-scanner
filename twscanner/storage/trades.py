"""
已實現交易紀錄的持久化：本機 ~/.tw_scanner_trades.json；登入雲端時同步存到 Neon（tw_kv）。
"""
import json
from pathlib import Path

from twscanner.storage import cloud

TRADES_PATH = Path.home() / ".tw_scanner_trades.json"
_KEY = "trades"


def load_records(owner=None):
    if owner and cloud.is_enabled():
        recs = cloud.kv_get(owner, _KEY)
        if recs is not None:
            return list(recs)
    try:
        return json.loads(TRADES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_records(records, owner=None):
    ok = True
    try:
        TRADES_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=1, default=str),
                               encoding="utf-8")
    except Exception:
        ok = False
    if owner and cloud.is_enabled():
        ok = bool(cloud.kv_set(owner, _KEY, records)) and ok
    return ok
