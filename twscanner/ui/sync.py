"""
雲端同步管理（登入後自動，不用按「存到雲端」）。

同步四份資料：持股、交易紀錄、訊號日誌、設定。流程：
- 登入：一次查詢讀回全部（kv_get_all），套用到這個 session；這台登入前就有、雲端沒有的資料會上傳。
- 每次頁面執行開頭（最多每 45 秒一次）：只讀版本號，別台裝置改過且這台沒改 → 自動拉回。
- 每次頁面執行結尾：內容有變的才上傳，並帶上版本號；雲端已被別台改過就不覆蓋，改成「衝突」。
- 衝突：交易紀錄、訊號日誌自動合併；持股與設定在頁面上方讓使用者選要用哪一邊。
- 登出：清掉這個 session 裡的個人資料（共用電腦時下一個人看不到）。
判斷邏輯在 twscanner/storage/sync.py（純函式、有測試）。
"""
import time

import pandas as pd
import streamlit as st

from twscanner.core.tz import now_tw
from twscanner.portfolio import trade_log
from twscanner.storage import cloud as store
from twscanner.storage.sync import MERGEABLE, decide, is_empty, merge, signature

KEYS = ("holdings", "trades", "journal", "prefs")
LABELS = {"holdings": "持股", "trades": "交易紀錄", "journal": "訊號日誌", "prefs": "設定"}
# 跟著帳號走的設定（換裝置也一樣）。上傳清單的檔案不同步，所以不含 scan_source。
SETTING_KEYS = (
    "preset", "total_capital", "month_target", "loss_limit_r", "color_mode", "strategy_mode", "universe_kind",
    "risk_pct", "max_pos_pct", "f_atr_mult", "_max_adv_pct_pct", "max_adv_pct",
    "min_price", "min_avg_volume", "require_ma60", "min_risk_pct", "min_risk_pct_slider", "amb_rs_gate", "amb_min_rs",
    "w_breakout", "w_ma", "w_turnover", "w_kd", "w_macd", "w_rs", "w_trend", "thr_enter", "thr_watch",
    "cost_enabled", "cost_fee", "cost_disc", "cost_tax", "cost_slip", "cost_apply_fe", "last_calibrated_date",
)
PERSONAL_KEYS = ("holdings_df", "_holdings_edited", "holdings_result", "holdings_analyzed_at", "trades_df",
                 "journal", "journal_eval", "total_capital", "month_target", "loss_limit_r")
CHECK_EVERY_SEC = 45


def _ss():
    return st.session_state


def owner():
    return _ss().get("cloud_owner") if store.is_enabled() else None


def _meta():
    return _ss().setdefault("_sync", {"keys": {}, "conflicts": {}, "last_ok": None, "error": None, "checked": 0})


# ---------- 這台的資料 ↔ 可存進雲端的 JSON ----------
def snapshot(key):
    """這台目前的內容（JSON 可存）；還沒載入過的回 None（不同步）。"""
    ss = _ss()
    if key == "holdings":
        df = ss.get("_holdings_edited", ss.get("holdings_df"))
        return store.holdings_to_records(df)
    if key == "trades":
        df = ss.get("trades_df")
        if df is None:
            return []
        return df.where(pd.notna(df), None).to_dict("records")
    if key == "journal":
        return list(ss.get("journal") or [])
    if key == "prefs":
        return {k: ss[k] for k in SETTING_KEYS if k in ss}
    return None


def apply(key, value):
    """把雲端內容套用到這個 session（只能在頁面畫出 widget 之前呼叫）。"""
    ss = _ss()
    if key == "holdings":
        ss["holdings_df"] = store.records_to_holdings(value)
        ss.pop("_holdings_edited", None)
        ss.pop("holdings_result", None)
        ss["holdings_editor_version"] = ss.get("holdings_editor_version", 0) + 1
    elif key == "trades":
        df = pd.DataFrame(value or [])
        for c in trade_log.COLUMNS:
            if c not in df.columns:
                df[c] = None
        ss["trades_df"] = df[trade_log.COLUMNS].astype({"股票代號": str})
    elif key == "journal":
        ss["journal"] = list(value or [])
        ss.pop("journal_eval", None)
    elif key == "prefs":
        for k, v in (value or {}).items():
            if k in SETTING_KEYS:
                ss[k] = v
        ss["_prefs"] = {**ss.get("_prefs", {}), **(value or {})}


def _set_base(key, value, at):
    _meta()["keys"][key] = {"sig": signature(value), "at": at}


def _ok():
    m = _meta()
    m["last_ok"] = now_tw().strftime("%H:%M")
    m["error"] = None


def _fail():
    _meta()["error"] = store.last_error or "連不上雲端"


# ---------- 登入、定期檢查、上傳 ----------
def on_login():
    """登入後第一次執行：讀回全部、合併這台登入前的資料。失敗就下次再試。"""
    o = owner()
    if not o or _ss().get("_cloud_loaded"):
        return
    rows = store.kv_get_all(o)
    if rows is None:
        _fail()
        return
    m = _meta()
    for key in KEYS:
        remote = rows.get(key)
        local = snapshot(key)
        if remote is None:
            _set_base(key, None, None)                 # 雲端沒有：這台有資料就會在結尾上傳
            if is_empty(local):
                _set_base(key, local, None)
            continue
        rv = remote["value"]
        if is_empty(local) or signature(local) == signature(rv) or key == "prefs":
            apply(key, rv)
            _set_base(key, rv, remote["at"])
        elif key in MERGEABLE:
            apply(key, merge(key, local, rv))           # 結尾會把合併結果上傳
            _set_base(key, rv, remote["at"])
        else:                                          # 持股：兩邊不一樣，請使用者選
            _set_base(key, local, remote["at"])
            m["conflicts"][key] = {"remote": rv, "at": remote["at"]}
    _ss()["_cloud_loaded"] = True
    m["checked"] = time.time()
    _ok()


def pull_changes(force=False):
    """別台裝置改過的資料拉回來（只讀版本號，很輕；最多每 45 秒一次）。"""
    o = owner()
    m = _meta()
    if not o or not _ss().get("_cloud_loaded"):
        return
    if not force and time.time() - m.get("checked", 0) < CHECK_EVERY_SEC:
        return
    m["checked"] = time.time()
    versions = store.kv_versions(o)
    if versions is None:
        _fail()
        return
    changed = [k for k in KEYS if k not in m["conflicts"]
               and decide(signature(snapshot(k)), m["keys"].get(k), versions.get(k)) in ("pull", "conflict")]
    if not changed:
        return
    rows = store.kv_get_all(o) or {}
    for key in changed:
        remote = rows.get(key)
        if not remote:
            continue
        action = decide(signature(snapshot(key)), m["keys"].get(key), remote["at"])
        if action == "pull":
            apply(key, remote["value"])
            _set_base(key, remote["value"], remote["at"])
            st.toast(f"已從雲端更新{LABELS[key]}（另一台裝置的修改）")
        elif action == "conflict":
            _conflict(key, remote["value"], remote["at"])
    _ok()


def _conflict(key, remote_value, remote_at):
    m = _meta()
    if key in MERGEABLE:
        apply(key, merge(key, snapshot(key), remote_value))
        m["keys"][key] = {**m["keys"].get(key, {}), "at": remote_at}   # 合併結果下次以新版本上傳
    else:
        m["conflicts"][key] = {"remote": remote_value, "at": remote_at}
        st.toast(f"「{LABELS[key]}」另一台裝置也改過了：請在頁面最上方選要保留哪一份")


def push_changes():
    """有變的才上傳。在頁面執行結尾呼叫（包括 st.rerun 之前）。回傳是否出現新的衝突（要重畫頁面讓使用者選）。"""
    o = owner()
    if not o or not _ss().get("_cloud_loaded"):
        return False
    m = _meta()
    before = set(m["conflicts"])
    for key in KEYS:
        if key in m["conflicts"]:
            continue
        value = snapshot(key)
        base = m["keys"].get(key, {})
        if signature(value) == base.get("sig"):
            continue
        res = store.kv_put(o, key, value, expect_at=base.get("at"))
        if res["ok"]:
            _set_base(key, value, res["at"])
            _ok()
        elif res["conflict"]:
            _conflict(key, res["remote"], res["at"])
        else:
            _fail()
            break                                          # 連不上就先停，下次執行會再試
    return bool(set(m["conflicts"]) - before)


def resolve(key, use):
    """衝突處理（按鈕的 on_click）：use="cloud" 用雲端版本、"local" 用這台的版本覆蓋雲端。"""
    m = _meta()
    c = m["conflicts"].pop(key, None)
    if not c:
        return
    if use == "cloud":
        apply(key, c["remote"])
        _set_base(key, c["remote"], c["at"])
    else:
        value = snapshot(key)
        res = store.kv_put(owner(), key, value, force=True)
        if res["ok"]:
            _set_base(key, value, res["at"])
            _ok()
        else:
            m["conflicts"][key] = c
            _fail()


def logout():
    """登出並清掉這個 session 的個人資料。"""
    ss = _ss()
    for k in ("cloud_owner", "_cloud_loaded", "_sync", "_hold_sig") + PERSONAL_KEYS:
        ss.pop(k, None)


def status():
    """給頁首：(文字, 狀態)。狀態：ok / error / conflict / off / local。"""
    if not store.is_enabled():
        return None, "off"
    if not owner():
        return "未登入雲端：資料只在這個分頁", "local"
    m = _meta()
    if m["conflicts"]:
        return "雲端有衝突：請在頁面最上方選要保留哪一份", "conflict"
    if m["error"]:
        return "雲端同步中斷，稍後自動重試", "error"
    return (f"已同步 {m['last_ok']}" if m["last_ok"] else "已登入雲端"), "ok"


def render_conflicts():
    """持股或設定兩邊都改過時，在頁面最上方讓使用者選。"""
    m = _meta() if owner() else {"conflicts": {}}
    for key, c in list(m["conflicts"].items()):
        with st.container(key=f"sync_conflict_{key}"):
            st.warning(f"「{LABELS[key]}」在另一台裝置也改過了，兩邊內容不一樣。要用哪一份？")
            a, b, _ = st.columns([1, 1, 2])
            a.button("用雲端的版本", key=f"sync_cloud_{key}", on_click=resolve, args=(key, "cloud"),
                     use_container_width=True)
            b.button("用這台的版本", key=f"sync_local_{key}", on_click=resolve, args=(key, "local"),
                     use_container_width=True)
