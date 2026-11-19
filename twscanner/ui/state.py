"""Streamlit 狀態與快取：設定/大盤/美股/代號名稱的快取載入、雲端登入、偏好、session 初始化。"""

import pandas as pd
import streamlit as st

from twscanner.core.config import load_config
from twscanner.core.tz import today_tw
from twscanner.data.universe import fetch_twse_universe
from twscanner.market.tw_regime import classify_market
from twscanner.market.us_regime import classify_us_market
from twscanner.portfolio import journal, trade_log
from twscanner.storage import cloud as store
from twscanner.storage import trades as trades_store
from twscanner.storage.preferences import load_prefs, save_prefs


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
    owner = cloud_owner()
    if owner and store.is_enabled():
        store.save_holdings(owner, st.session_state["holdings_df"])


def get_trades_df():
    """已實現交易紀錄（原始欄位）。第一次讀取時從本機 / 雲端載入。"""
    if "trades_df" not in st.session_state:
        recs = trades_store.load_records(cloud_owner())
        df = pd.DataFrame(recs) if recs else trade_log.empty()
        for c in trade_log.COLUMNS:
            if c not in df.columns:
                df[c] = None
        st.session_state["trades_df"] = df[trade_log.COLUMNS].astype({"股票代號": str})
    return st.session_state["trades_df"]


def save_trades_df(df):
    df = df[[c for c in trade_log.COLUMNS if c in df.columns]].copy()
    st.session_state["trades_df"] = df
    recs = df.where(pd.notna(df), None).to_dict("records")
    return trades_store.save_records(recs, cloud_owner())


@st.cache_data(ttl=86400, show_spinner=False)
def get_sector_map():
    """{代號: 產業}（組合風險的產業集中度用）。"""
    from twscanner.data.sectors import fetch_sectors
    cfg = get_base_config()
    try:
        return fetch_sectors(cfg["data"]["cache_dir"])
    except Exception:
        return {}
