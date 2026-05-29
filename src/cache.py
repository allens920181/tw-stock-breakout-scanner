import os
import pickle
from datetime import date

import pandas as pd


def _today():
    return date.today().strftime("%Y%m%d")


def _path(cache_dir, symbol, kind, ext):
    safe = symbol.replace(".", "_")
    return os.path.join(cache_dir, f"{safe}_{kind}_{_today()}.{ext}")


def ensure_dir(cache_dir):
    os.makedirs(cache_dir, exist_ok=True)


def load_df(cache_dir, symbol, kind):
    """嘗試 parquet → pickle"""
    for ext in ("parquet", "pkl"):
        path = _path(cache_dir, symbol, kind, ext)
        if not os.path.exists(path):
            continue
        try:
            if ext == "parquet":
                return pd.read_parquet(path)
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            continue
    return None


def save_df(cache_dir, symbol, kind, df):
    path = _path(cache_dir, symbol, kind, "parquet")
    try:
        df.to_parquet(path)
        return
    except Exception:
        pass
    alt = _path(cache_dir, symbol, kind, "pkl")
    with open(alt, "wb") as f:
        pickle.dump(df, f)


def load_obj(cache_dir, key):
    path = os.path.join(cache_dir, f"{key}_{_today()}.pkl")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def save_obj(cache_dir, key, obj):
    path = os.path.join(cache_dir, f"{key}_{_today()}.pkl")
    with open(path, "wb") as f:
        pickle.dump(obj, f)
