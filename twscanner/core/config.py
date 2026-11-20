"""設定檔載入。相對路徑找不到時，回退到專案根目錄（可從任何工作目錄執行）。"""
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = "config.yaml"


def resolve_path(path):
    p = Path(path)
    if p.exists() or p.is_absolute():
        return p
    alt = PROJECT_ROOT / p
    return alt if alt.exists() else p


def load_config(path=DEFAULT_CONFIG):
    p = resolve_path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到設定檔：{p.resolve()}")
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
