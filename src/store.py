# -*- coding: utf-8 -*-
"""
雲端持久化（Neon / 任意 PostgreSQL）— 單人會員空間用。

設計：
- 「加上去、不破壞」：未設定 DATABASE_URL 時 is_enabled()=False，App 行為與原本完全一致。
- 一張 KV 表 tw_kv(owner, key, value jsonb)：holdings / journal / prefs / watchlist 各存一個 JSONB blob。
- 全程容錯：任何 DB 錯誤都記 log 並回退安全預設，永不讓 App 崩潰。
- psycopg2 延遲 import：本機沒裝也能 import 本模組（雲端 requirements 會裝）。
"""
import json
import logging

log = logging.getLogger(__name__)

_DSN = None
_SCHEMA_READY = False

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS tw_kv (
    owner       text NOT NULL,
    key         text NOT NULL,
    value       jsonb NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (owner, key)
);
"""


def configure(dsn):
    """由 App 啟動時帶入 Neon 連線字串（取自 st.secrets）。None/空 → 停用雲端。"""
    global _DSN, _SCHEMA_READY
    _DSN = (dsn or "").strip() or None
    _SCHEMA_READY = False


def is_enabled():
    return bool(_DSN)


def _conn():
    import psycopg2  # 延遲載入
    return psycopg2.connect(_DSN, connect_timeout=10)


def _ensure_schema(cur):
    global _SCHEMA_READY
    if not _SCHEMA_READY:
        cur.execute(_CREATE_SQL)
        _SCHEMA_READY = True


def kv_get(owner, key, default=None):
    if not _DSN:
        return default
    try:
        with _conn() as conn, conn.cursor() as cur:
            _ensure_schema(cur)
            cur.execute("SELECT value FROM tw_kv WHERE owner=%s AND key=%s", (owner, key))
            row = cur.fetchone()
            return row[0] if row else default
    except Exception as e:
        log.warning("雲端讀取失敗（%s/%s）：%s", owner, key, e)
        return default


def kv_set(owner, key, value):
    if not _DSN:
        return False
    try:
        payload = json.dumps(value, ensure_ascii=False, default=str)
        with _conn() as conn, conn.cursor() as cur:
            _ensure_schema(cur)
            cur.execute(
                "INSERT INTO tw_kv (owner, key, value) VALUES (%s, %s, %s) "
                "ON CONFLICT (owner, key) DO UPDATE SET value=EXCLUDED.value, "
                "updated_at=now()",
                (owner, key, payload),
            )
        return True
    except Exception as e:
        log.warning("雲端寫入失敗（%s/%s）：%s", owner, key, e)
        return False


# ========== 持股（DataFrame <-> records）==========
_HOLD_COLS = ["股票代號", "公司名稱", "進場價", "進場日", "持有張數"]


def holdings_to_records(df):
    """DataFrame → list[dict]（進場日轉字串以利 JSON）。"""
    import pandas as pd
    if df is None or len(df) == 0:
        return []
    out = []
    for _, row in df.iterrows():
        rec = {}
        for c in _HOLD_COLS:
            v = row.get(c) if hasattr(row, "get") else (row[c] if c in row else None)
            if isinstance(v, pd.Timestamp):
                v = v.strftime("%Y-%m-%d")
            elif isinstance(v, float) and pd.isna(v):
                v = None
            rec[c] = v
        out.append(rec)
    return out


def records_to_holdings(records):
    """list[dict] → DataFrame（進場日轉回 Timestamp）。"""
    import pandas as pd
    if not records:
        return pd.DataFrame(columns=_HOLD_COLS)
    df = pd.DataFrame(records)
    for c in _HOLD_COLS:
        if c not in df.columns:
            df[c] = None
    try:
        df["進場日"] = pd.to_datetime(df["進場日"], errors="coerce")
    except Exception:
        pass
    return df[_HOLD_COLS]


def save_holdings(owner, df):
    return kv_set(owner, "holdings", holdings_to_records(df))


def load_holdings(owner):
    """回 DataFrame；雲端無資料回 None（讓 App 維持現有 session 預設）。"""
    rec = kv_get(owner, "holdings", None)
    if rec is None:
        return None
    return records_to_holdings(rec)


# ========== 訊號日誌 / 偏好 ==========
def save_journal(owner, records):
    return kv_set(owner, "journal", records or [])


def load_journal(owner):
    return kv_get(owner, "journal", None)


def save_prefs(owner, prefs):
    return kv_set(owner, "prefs", prefs or {})


def load_prefs(owner):
    return kv_get(owner, "prefs", None)
