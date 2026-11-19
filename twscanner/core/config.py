from pathlib import Path
import yaml


def load_config(path="config.yaml"):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到設定檔：{p.resolve()}")
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
