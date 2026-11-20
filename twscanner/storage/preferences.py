"""
使用者偏好。

分兩類，存放位置不同：
- 一般設定（風格、漲跌顏色、上次校準日）：存本機 ~/.tw_scanner_prefs.json。
- 個人財務數字（總資金、月目標、每月虧損上限）：只存登入後的雲端空間（Neon）。
  公開部署時伺服器檔案是所有訪客共用的，財務數字寫進去等於公開；舊檔若含這些欄位會在讀取時清掉。
"""
import json
from pathlib import Path

from twscanner.storage import cloud

PREF_PATH = Path.home() / ".tw_scanner_prefs.json"
PRIVATE_KEYS = ("total_capital", "month_target", "loss_limit_r")

DEFAULTS = {
    "preset": "balanced",
    "total_capital": 1_000_000,
    "month_target": 10_000,
    "loss_limit_r": 2.0,
    "color_mode": "tw",
    "onboarded": False,
}


def _public(data):
    return {k: v for k, v in (data or {}).items() if k not in PRIVATE_KEYS}


def _read_local():
    if not PREF_PATH.exists():
        return {}
    try:
        data = json.loads(PREF_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if any(k in data for k in PRIVATE_KEYS):        # 舊版把財務數字寫進共用檔 → 清掉
        _write_local(_public(data))
        data = _public(data)
    return data


def _write_local(data):
    try:
        PREF_PATH.write_text(json.dumps(_public(data), ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def load_prefs(owner=None):
    """預設值 ← 本機一般設定 ← 雲端（登入時，含財務數字）。"""
    merged = DEFAULTS.copy()
    merged.update(_read_local())
    if owner and cloud.is_enabled():
        remote = cloud.load_prefs(owner)
        if remote:
            merged.update(remote)
    return merged


def save_prefs(data, owner=None):
    """
    回 {"local": bool, "cloud": bool}：一般設定寫本機；登入時全部（含財務數字）寫雲端。
    未登入時財務數字不會被保存。
    """
    local_ok = _write_local(data)
    cloud_ok = bool(owner and cloud.is_enabled() and cloud.save_prefs(owner, data))
    return {"local": local_ok, "cloud": cloud_ok}
