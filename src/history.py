"""歷史掃描紀錄：每次掃描完自動存一份摘要到 .cache/scans/"""
import json
import os
from pathlib import Path

import pandas as pd

from .tz import now_tw

SCANS_DIR = Path(".cache") / "scans"


def _ensure_dir():
    SCANS_DIR.mkdir(parents=True, exist_ok=True)


def save_scan(result, market_state=None, label=None):
    """存當次掃描結果（df + summary + meta）"""
    _ensure_dir()
    ts = now_tw().strftime("%Y%m%d_%H%M%S")
    base = SCANS_DIR / ts

    df = result.get("df")
    summary = result.get("summary")

    if df is not None and len(df):
        try:
            df.to_parquet(str(base) + ".parquet")
        except Exception:
            df.to_pickle(str(base) + ".pkl")

    meta = {
        "timestamp": ts,
        "label": label or "",
        "elapsed_sec": result.get("elapsed_sec"),
        "market": market_state.get("label") if market_state else None,
        "n_total": int(summary.iloc[0]["掃描股票數"]) if summary is not None and len(summary) else 0,
        "n_enter": int(summary.iloc[0].get("進場檔數", 0)) if summary is not None and len(summary) else 0,
        "n_watch": int(summary.iloc[0].get("觀察檔數", 0)) if summary is not None and len(summary) else 0,
    }
    with open(str(base) + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def list_scans():
    if not SCANS_DIR.exists():
        return []
    metas = []
    for p in sorted(SCANS_DIR.glob("*.json"), reverse=True):
        try:
            with open(p, "r", encoding="utf-8") as f:
                m = json.load(f)
            m["_path"] = str(p.with_suffix(""))  # 無附檔名 base
            metas.append(m)
        except Exception:
            continue
    return metas


def load_scan_df(base_path):
    p1 = Path(base_path + ".parquet")
    p2 = Path(base_path + ".pkl")
    if p1.exists():
        return pd.read_parquet(p1)
    if p2.exists():
        return pd.read_pickle(p2)
    return None


def cleanup_old(keep_n=30):
    """只保留最近 N 份"""
    if not SCANS_DIR.exists():
        return
    metas = sorted(SCANS_DIR.glob("*.json"), reverse=True)
    for old in metas[keep_n:]:
        base = old.with_suffix("")
        for ext in (".json", ".parquet", ".pkl"):
            f = Path(str(base) + ext)
            if f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass
