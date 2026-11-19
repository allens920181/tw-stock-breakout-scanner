"""使用者偏好持久化到 ~/.tw_scanner_prefs.json"""
import json
from pathlib import Path

PREF_PATH = Path.home() / ".tw_scanner_prefs.json"

DEFAULTS = {
    "preset": "balanced",
    "total_capital": 1_000_000,
    "onboarded": False,
}


def load_prefs():
    if not PREF_PATH.exists():
        return DEFAULTS.copy()
    try:
        with open(PREF_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = DEFAULTS.copy()
        merged.update(data)
        return merged
    except Exception:
        return DEFAULTS.copy()


def save_prefs(data):
    try:
        with open(PREF_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
