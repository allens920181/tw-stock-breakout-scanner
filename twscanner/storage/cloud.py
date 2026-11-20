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
import threading

log = logging.getLogger(__name__)

_DSN = None
_SCHEMA_READY = False
last_error = None     # 最近一次 DB 操作的錯誤訊息（給診斷用）

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
    """由 App 啟動時帶入 Neon 連線字串（取自 st.secrets）。None/空 → 停用雲端。同一字串重複呼叫不會斷線。"""
    global _DSN, _SCHEMA_READY, _CONN
    dsn = (dsn or "").strip() or None
    if dsn == _DSN:
        return
    _close()
    _DSN = dsn
    _SCHEMA_READY = False


def is_enabled():
    return bool(_DSN)


def _connect():
    """雙驅動容錯：優先 psycopg2，沒有就用純 Python 的 pg8000（任何平台都裝得起）。"""
    try:
        import psycopg2
        return psycopg2.connect(_DSN, connect_timeout=10)
    except ImportError:
        pass
    import ssl
    from urllib.parse import urlparse

    import pg8000.dbapi
    u = urlparse(_DSN)
    kw = {}
    if u.hostname not in ("localhost", "127.0.0.1"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kw["ssl_context"] = ctx
    return pg8000.dbapi.connect(
        user=u.username, password=u.password,
        host=u.hostname, port=u.port or 5432,
        database=(u.path or "/").lstrip("/"), timeout=15, **kw,
    )


# ---- 共用連線：每次讀寫都重新連線很慢（Neon 冷啟動 1–3 秒）。一條連線加鎖共用，斷了就重連一次 ----
_CONN = None
_LOCK = threading.RLock()


def _close():
    global _CONN
    try:
        if _CONN is not None:
            _CONN.close()
    except Exception:
        pass
    _CONN = None


def _run(fn):
    """在共用連線上執行 fn(cursor)；失敗（多半是閒置被斷線）就重連重試一次。"""
    global _CONN, _SCHEMA_READY
    with _LOCK:
        for attempt in (1, 2):
            try:
                if _CONN is None:
                    _CONN = _connect()
                cur = _CONN.cursor()
                if not _SCHEMA_READY:
                    cur.execute(_CREATE_SQL)
                    _SCHEMA_READY = True
                out = fn(cur)
                _CONN.commit()
                return out
            except ImportError:
                raise
            except Exception:
                try:
                    _CONN.rollback()
                except Exception:
                    pass
                _close()
                _SCHEMA_READY = False
                if attempt == 2:
                    raise


def _coerce(val):
    """jsonb 回傳：psycopg2 給 dict/list、pg8000 給字串 → 統一成 Python 物件。"""
    if isinstance(val, (str, bytes)):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val


def _ts(v):
    """timestamptz → ISO 字串（當作版本號比對，精確到微秒）。"""
    return v.isoformat() if hasattr(v, "isoformat") else (str(v) if v is not None else None)


def ping():
    """測試連線：回 (ok: bool, msg: str)。給 UI 顯示『到底連上沒』。"""
    global last_error
    if not _DSN:
        return False, "未設定 DATABASE_URL"
    try:
        _run(lambda cur: (cur.execute("SELECT 1"), cur.fetchone()))
        last_error = None
        return True, "連線正常"
    except ImportError:
        last_error = "未安裝資料庫驅動（psycopg2 / pg8000）"
        return False, last_error
    except Exception as e:
        last_error = str(e)
        return False, str(e)


def kv_get_all(owner):
    """一次讀回這個人的全部資料：{key: {"value": ..., "at": 版本}}；失敗回 None（不是空 dict）。"""
    global last_error
    if not _DSN:
        return None

    def q(cur):
        cur.execute("SELECT key, value, updated_at FROM tw_kv WHERE owner=%s", (owner,))
        return {k: {"value": _coerce(v), "at": _ts(t)} for k, v, t in cur.fetchall()}
    try:
        out = _run(q)
        last_error = None
        return out
    except Exception as e:
        last_error = str(e)
        log.warning("雲端讀取失敗（%s）：%s", owner, e)
        return None


def kv_versions(owner):
    """只讀版本（不帶內容，很輕）：{key: at}；用來偵測別台裝置是否改過。失敗回 None。"""
    global last_error
    if not _DSN:
        return None

    def q(cur):
        cur.execute("SELECT key, updated_at FROM tw_kv WHERE owner=%s", (owner,))
        return {k: _ts(t) for k, t in cur.fetchall()}
    try:
        return _run(q)
    except Exception as e:
        last_error = str(e)
        return None


def kv_put(owner, key, value, expect_at=None, force=False):
    """
    寫入並回 {"ok", "at", "conflict", "remote"}。
    expect_at：上次讀到的版本。雲端版本已經不同（別台裝置改過）就不覆蓋，回 conflict=True 與雲端內容。
    force=True 直接覆蓋（使用者選「用這台的版本」時）。
    """
    global last_error
    if not _DSN:
        last_error = "未設定 DATABASE_URL"
        return {"ok": False, "at": None, "conflict": False, "remote": None}
    payload = json.dumps(value, ensure_ascii=False, default=str)

    def q(cur):
        if not force and expect_at is not None:
            cur.execute("UPDATE tw_kv SET value=%s::jsonb, updated_at=clock_timestamp() "
                        "WHERE owner=%s AND key=%s AND updated_at=%s::timestamptz RETURNING updated_at",
                        (payload, owner, key, expect_at))
            row = cur.fetchone()
            if row:
                return {"ok": True, "at": _ts(row[0]), "conflict": False, "remote": None}
        if not force:
            cur.execute("SELECT value, updated_at FROM tw_kv WHERE owner=%s AND key=%s", (owner, key))
            row = cur.fetchone()
            if row:   # 雲端已有、而且版本不是我們讀到的那個 → 衝突
                return {"ok": False, "at": _ts(row[1]), "conflict": True, "remote": _coerce(row[0])}
        cur.execute("INSERT INTO tw_kv (owner, key, value) VALUES (%s, %s, %s::jsonb) "
                    "ON CONFLICT (owner, key) DO UPDATE SET value=EXCLUDED.value, updated_at=clock_timestamp() "
                    "RETURNING updated_at", (owner, key, payload))
        return {"ok": True, "at": _ts(cur.fetchone()[0]), "conflict": False, "remote": None}
    try:
        out = _run(q)
        last_error = None
        return out
    except Exception as e:
        last_error = str(e)
        log.warning("雲端寫入失敗（%s/%s）：%s", owner, key, e)
        return {"ok": False, "at": None, "conflict": False, "remote": None}


def kv_get(owner, key, default=None):
    rows = kv_get_all(owner)
    if not rows or key not in rows:
        return default
    return rows[key]["value"]


def kv_set(owner, key, value):
    return kv_put(owner, key, value, force=True)["ok"]


# ========== 持股（DataFrame <-> records）==========
# 欄位須與持股編輯器一致：股票代號 / 公司名稱 / 成本價 / 持有股數
_HOLD_COLS = ["股票代號", "公司名稱", "成本價", "持有股數"]


def holdings_to_records(df):
    """DataFrame → list[dict]。只保留持股編輯器的 4 個欄位。"""
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
    """list[dict] → DataFrame，只回 4 個正規欄位（多餘欄如舊『進場日』自動丟棄）。"""
    import pandas as pd
    if not records:
        return pd.DataFrame(columns=_HOLD_COLS)
    df = pd.DataFrame(records)
    for c in _HOLD_COLS:
        if c not in df.columns:
            df[c] = None
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
