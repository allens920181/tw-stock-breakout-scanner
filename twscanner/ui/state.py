"""Streamlit 狀態與快取：設定/大盤/美股/代號名稱的快取載入、雲端登入、偏好、session 初始化。"""

import pandas as pd
import streamlit as st

from twscanner.core.config import load_config
from twscanner.core.tz import today_tw
from twscanner.data.universe import fetch_twse_universe
from twscanner.market.recovery import fetch_recovery
from twscanner.market.tw_regime import classify_market
from twscanner.market.us_regime import classify_us_market
from twscanner.portfolio import trade_log
from twscanner.storage import cloud as store
from twscanner.storage.preferences import load_prefs, save_prefs
from twscanner.ui import auth, sync


@st.cache_data
def get_base_config():
    return load_config("config.yaml")


class _NotReady(Exception):
    """資料暫時抓不到：丟例外讓 st.cache_data 不要把「未知」快取起來。"""


@st.cache_data(ttl=600, show_spinner=False)
def _market_state():
    cfg = get_base_config()
    r = classify_market(cfg["data"]["period"], cfg["data"]["cache_dir"])
    if not r or r.get("regime") in (None, "unknown"):
        raise _NotReady()
    return r


@st.cache_data(ttl=1800, show_spinner=False)
def _us_state():
    r = classify_us_market("1y", get_base_config()["data"]["cache_dir"])
    if not r or r.get("regime") in (None, "unknown"):
        raise _NotReady()
    return r


def get_market_state_cached():
    """台股大盤狀態；暫時抓不到時回 unknown，且不快取（下次互動會重試）。"""
    try:
        return _market_state()
    except Exception:
        return {"regime": "unknown", "label": "未知", "position_factor": 1.0, "detail": "大盤資料暫時抓不到"}


def get_us_state_cached():
    try:
        return _us_state()
    except Exception:
        return {"regime": "unknown", "label": "未知", "position_factor": 1.0, "detail": "美股資料暫時抓不到"}


@st.cache_data(ttl=1800, show_spinner=False)
def _recovery():
    cfg = get_base_config()
    return fetch_recovery(cfg["data"]["cache_dir"], cfg["data"]["period"])


def get_recovery_cached():
    """止跌訊號與劇本線索；整體失敗回 None（個別來源失敗會在項目內顯示「暫無資料」）。"""
    try:
        return _recovery()
    except Exception:
        return None


@st.cache_data(ttl=86400)
def get_code_name_map():
    """從 TWSE OpenAPI 抓代號 → 名稱 對照表（一天快取）"""
    try:
        uni = fetch_twse_universe(include_common=True, include_etf=True)
        return {x["code"]: x["company_name"] for x in uni}
    except Exception:
        return {}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def get_universe_items(kind):
    """全台股清單（twse / twse-common / twse-etf）→ [{code, company_name}]；失敗丟例外（不快取）。"""
    raw = fetch_twse_universe(include_common=kind in ("twse", "twse-common"),
                              include_etf=kind in ("twse", "twse-etf"))
    if not raw:
        raise _NotReady("全台股清單暫時抓不到")
    return [{"code": x["code"], "company_name": x["company_name"]} for x in raw]


def current_pool():
    """今天的資料池（跨日就作廢：價格與籌碼每天都會變）。"""
    p = st.session_state.get("data_pool")
    if p and p.get("date") == today_tw().isoformat():
        return p["data"]
    return None


def save_pool(pool, fetched_at):
    st.session_state["data_pool"] = {"date": today_tw().isoformat(), "at": fetched_at, "data": pool}


def cloud_owner():
    return st.session_state.get("cloud_owner")


def persist_calibration_date():
    """記錄並持久化本次校準日期（給頻率提醒用）。"""
    d = today_tw().isoformat()
    st.session_state["last_calibrated_date"] = d
    try:
        _p = load_prefs(None)
        _p["last_calibrated_date"] = d
        save_prefs(_p, None)          # 本機；登入時由雲端同步帶走（ui/sync.py 的 SETTING_KEYS）
    except Exception:
        pass


# =====================================================
# 雲端會員空間（Neon）：未設定 secrets → 停用，App 行為與原本完全一致
# =====================================================
def _secret(key):
    try:
        return st.secrets.get(key, "")
    except Exception:
        return ""


def cloud_passcode():
    return _secret("APP_PASSCODE")


def get_prefs():
    """本 session 載入的使用者偏好（bootstrap 後可用）。"""
    return st.session_state.get("_prefs") or load_prefs(None)


def _load_prefs_once():
    if "_prefs_loaded" in st.session_state:
        return
    prefs = load_prefs(None)          # 本機一般設定；登入後的雲端設定由 ui/sync.py 套用
    st.session_state["_prefs"] = prefs
    st.session_state["_prefs_loaded"] = True
    # 跨重啟保留「上次校準日期」以維持頻率提醒
    if prefs.get("last_calibrated_date") and "last_calibrated_date" not in st.session_state:
        st.session_state["last_calibrated_date"] = prefs["last_calibrated_date"]


# 跨頁要保留的設定（widget 的值）。多頁導覽下，widget 不在本頁時 Streamlit 會清掉它的值；
# 每次 rerun 開頭把值「重新指定」一次，就會變成一般 session 值而保留下來。
PERSIST_KEYS = (
    "scan_source", "universe_kind", "strategy_mode",
    "month_target", "loss_limit_r", "total_capital", "risk_pct", "max_pos_pct", "f_atr_mult",
    "_max_adv_pct_pct", "min_price", "min_avg_volume", "require_ma60", "min_risk_pct_slider",
    "amb_rs_gate", "amb_min_rs", "w_breakout", "w_ma", "w_turnover", "w_kd", "w_macd", "w_rs", "w_trend",
    "thr_enter", "thr_watch", "color_mode",
    "cost_enabled", "cost_fee", "cost_disc", "cost_tax", "cost_slip", "cost_apply_fe", "stress_mult",
)


def persist_settings():
    for k in PERSIST_KEYS:
        if k in st.session_state:
            st.session_state[k] = st.session_state[k]


def seed(key, default):
    """widget 只給 key、不給 value：第一次用 default，之後沿用使用者的值（不會跳「同時設定」警告）。"""
    if key not in st.session_state:
        st.session_state[key] = default
    return key


def bootstrap():
    """每次 rerun 開頭呼叫：設定雲端、載入雲端資料/偏好、初始化 session 預設值。"""
    from twscanner.ui.settings import apply_preset  # 避免循環 import

    store.configure(_secret("DATABASE_URL") or None)
    auth.apply_login()               # Google 已登入（cookie 還在）→ 直接進雲端空間，不用再輸入密碼
    sync.on_login()
    _load_prefs_once()
    prefs = get_prefs()
    if "preset" not in st.session_state:
        apply_preset(prefs.get("preset", "balanced"))
        st.session_state["total_capital"] = int(prefs.get("total_capital", 1_000_000))
    for key, default in (("month_target", 10_000), ("loss_limit_r", 2.0), ("color_mode", "tw")):
        if key not in st.session_state:
            st.session_state[key] = prefs.get(key, default)


# =====================================================
# 持股與交易紀錄（今日決策、找標的、持股頁共用）
# =====================================================
def add_holding(code, name, cost, shares):
    """從交易計畫卡「我已買進」→ 加入持股編輯表（同代號則覆蓋成本與股數）。"""
    cols = ["股票代號", "公司名稱", "成本價", "持有股數"]
    df = st.session_state.get("holdings_df")
    if df is None:
        df = pd.DataFrame(columns=cols)
    df = df[[c for c in cols if c in df.columns]].copy()
    df = df[df["股票代號"].astype(str) != str(code)]
    row = pd.DataFrame([{"股票代號": str(code), "公司名稱": name, "成本價": float(cost),
                         "持有股數": int(shares)}])
    st.session_state["holdings_df"] = pd.concat([df, row], ignore_index=True)
    st.session_state["holdings_editor_version"] = st.session_state.get("holdings_editor_version", 0) + 1
    st.session_state.pop("_holdings_edited", None)      # 登入時由雲端同步自動上傳


def get_trades_df():
    """已實現交易紀錄（原始欄位）。只存在這個 session；登入時由雲端同步載入與上傳。"""
    if "trades_df" not in st.session_state:
        df = trade_log.empty()
        for c in trade_log.COLUMNS:
            if c not in df.columns:
                df[c] = None
        st.session_state["trades_df"] = df[trade_log.COLUMNS].astype({"股票代號": str})
    return st.session_state["trades_df"]


def save_trades_df(df):
    """寫回 session；回傳是否會保存到雲端（有登入才會，由同步在本次執行結尾上傳）。"""
    st.session_state["trades_df"] = df[[c for c in trade_log.COLUMNS if c in df.columns]].copy()
    return bool(cloud_owner())


def get_journal():
    """訊號日誌（只在 session 與登入後的雲端；不寫伺服器檔案，公開部署時才不會被別人看到）。"""
    return st.session_state.setdefault("journal", [])


def set_journal(records):
    st.session_state["journal"] = list(records or [])
    st.session_state.pop("journal_eval", None)


@st.cache_data(ttl=86400, show_spinner=False)
def get_sector_map():
    """{代號: 產業}（組合風險的產業集中度用）。"""
    from twscanner.data.sectors import fetch_sectors
    cfg = get_base_config()
    try:
        return fetch_sectors(cfg["data"]["cache_dir"])
    except Exception:
        return {}
