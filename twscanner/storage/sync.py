"""
雲端同步的判斷邏輯（純函式，不碰 Streamlit 也不連資料庫，方便測試）。

每一份資料（持股、交易紀錄、訊號日誌、設定）都記一個「基準」：上次和雲端一致時的內容指紋與雲端版本。
- 這台改了、雲端沒變 → 上傳（帶上版本，雲端若已被別台改過就不會覆蓋）
- 雲端變了、這台沒改 → 拉回來
- 兩邊都改了 → 交易紀錄與訊號日誌自動合併；持股與設定請使用者選
"""
import hashlib
import json

MERGEABLE = ("trades", "journal")


def signature(value):
    """內容指紋：同樣的資料（不論 key 順序）得到同樣的字串。"""
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def decide(local_sig, base, remote_at):
    """
    local_sig：這台目前的指紋；base：{"sig", "at"} 上次同步的基準；remote_at：雲端目前版本（沒有就 None）。
    回 "none" / "push" / "pull" / "conflict"。
    """
    base = base or {}
    local_changed = local_sig != base.get("sig")
    remote_changed = remote_at is not None and remote_at != base.get("at")
    if local_changed and remote_changed:
        return "conflict"
    if remote_changed:
        return "pull"
    if local_changed:
        return "push"
    return "none"


def _journal_key(r):
    return (r.get("掃描日"), r.get("股票"))


def merge(key, local, remote):
    """兩邊都改過時的自動合併：交易紀錄以整筆內容去重、訊號日誌以（掃描日, 股票）去重；保留本機順序。"""
    local, remote = list(local or []), list(remote or [])
    ident = _journal_key if key == "journal" else signature
    seen = {ident(r) for r in local}
    return local + [r for r in remote if ident(r) not in seen]


def is_empty(value):
    return value in (None, [], {})
