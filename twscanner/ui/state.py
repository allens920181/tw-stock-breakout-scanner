"""Streamlit 狀態與快取：設定/大盤/美股/代號名稱的快取載入、雲端登入、偏好、session 初始化。"""

import streamlit as st

from twscanner.core.config import load_config
from twscanner.core.tz import today_tw
from twscanner.data.universe import fetch_twse_universe
from twscanner.market.tw_regime import classify_market
from twscanner.market.us_regime import classify_us_market
from twscanner.portfolio import journal
from twscanner.storage import cloud as store
from twscanner.storage.preferences import load_prefs, save_prefs


@st.cache_data
def get_base_config():
    return load_config("config.yaml")


@st.cache_data(ttl=600)
def get_market_state_cached():
    cfg = get_base_config()
    return classify_market(cfg["data"]["period"], cfg["data"]["cache_dir"])


@st.cache_data(ttl=1800)
def get_us_state_cached():
    cfg = get_base_config()
    return classify_us_market("1y", cfg["data"]["cache_dir"])


@st.cache_data(ttl=86400)
def get_code_name_map():
    """從 TWSE OpenAPI 抓代號 → 名稱 對照表（一天快取）"""
    try:
        uni = fetch_twse_universe(include_common=True, include_etf=True)
        return {x["code"]: x["company_name"] for x in uni}
    except Exception:
        return {}


def cloud_owner():
    return st.session_state.get("cloud_owner")


def persist_calibration_date():
    """記錄並持久化本次校準日期（給頻率提醒用）。"""
    d = today_tw().isoformat()
    st.session_state["last_calibrated_date"] = d
    try:
        _p = load_prefs()
        _p["last_calibrated_date"] = d
        save_prefs(_p)
    except Exception:
        pass


def add_to_watchlist(code, name, entry, lots):
    existing = {w["code"] for w in st.session_state["watchlist"]}
    if code in existing:
        return False
    st.session_state["watchlist"].append({
        "code": code, "name": name, "entry": entry, "lots": lots,
    })
    return True


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
    return st.session_state.get("_prefs") or load_prefs()


def _load_cloud_once():
    """登入後一次性從雲端載入持股 / 訊號日誌。"""
    owner = cloud_owner()
    if not owner or st.session_state.get("_cloud_loaded"):
        return
    try:
        cdf = store.load_holdings(owner)
        if cdf is not None and len(cdf):
            st.session_state["holdings_df"] = cdf
            st.session_state["_hold_sig"] = cdf.to_json()
    except Exception:
        pass
    try:
        cj = store.load_journal(owner)
        if cj is not None:
            journal.save_journal(cj)          # 還原雲端日誌到本機工作檔
    except Exception:
        pass
    st.session_state["_cloud_loaded"] = True


def _load_prefs_once():
    if "_prefs_loaded" in st.session_state:
        return
    prefs = load_prefs()
    st.session_state["_prefs"] = prefs
    st.session_state["_prefs_loaded"] = True
    # 跨重啟保留「上次校準日期」以維持頻率提醒
    if prefs.get("last_calibrated_date") and "last_calibrated_date" not in st.session_state:
        st.session_state["last_calibrated_date"] = prefs["last_calibrated_date"]


def bootstrap():
    """每次 rerun 開頭呼叫：設定雲端、載入雲端資料/偏好、初始化 session 預設值。"""
    from twscanner.ui.settings import apply_preset  # 避免循環 import

    store.configure(_secret("DATABASE_URL") or None)
    _load_cloud_once()
    _load_prefs_once()
    prefs = get_prefs()
    if "preset" not in st.session_state:
        apply_preset(prefs.get("preset", "balanced"))
        st.session_state["total_capital"] = int(prefs.get("total_capital", 1_000_000))
    if "watchlist" not in st.session_state:
        st.session_state["watchlist"] = []
