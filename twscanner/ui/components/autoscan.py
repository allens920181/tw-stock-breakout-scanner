"""
排程結果（找標的頁、今日決策頁共用）。

GitHub Actions 每個交易日收盤後掃描，把進場與觀察名單存到雲端；這裡讀回最新一份，不必等掃描。
手動按「開始掃描」的背景執行在 twscanner/ui/actions.py（start_scan / apply_finished_scan / render_scan_banner）。
"""
import time

import streamlit as st

from twscanner.core.tz import now_tw
from twscanner.services.jobs import (
    MODE_LABELS,
    load_scan,
    payload_to_result,
    scan_key,
)
from twscanner.storage import cloud as store
from twscanner.ui.state import cloud_owner

CACHE_SEC = 60
SETUP = """**設定自動排程（只要做一次，約 5 分鐘）**

1. 需要先有雲端資料庫（設定頁 → 雲端帳號，說明在 `docs/雲端設定.md`）。
2. 到 GitHub 這個 repo → **Settings → Secrets and variables → Actions → New repository secret**，
   名稱填 `DATABASE_URL`，內容貼和 Streamlit Secrets 同一條 Neon 連線字串。
3. 到 **Actions → 排程掃描 → Run workflow** 手動跑一次確認成功（全台股約 10–15 分鐘）。
4. 之後每個交易日台灣時間 15:40 自動執行。要改時間，編輯 `.github/workflows/scheduled-scan.yml` 裡的 `cron`（UTC，台灣 = UTC+8）。

排程會同時算好三種策略與實證規則名單；執行失敗時 Actions 頁會顯示紅色叉叉（GitHub 預設也會寄通知信）。"""


def _fmt_at(iso):
    try:
        return now_tw().fromisoformat(iso).strftime("%m/%d %H:%M")
    except Exception:
        return str(iso)


def _payload(mode):
    """目前策略的排程結果；每個分頁最多 60 秒才查一次雲端。"""
    ss = st.session_state
    cache = ss.setdefault("_job_cache", {})
    hit = cache.get(mode)
    if hit and time.time() - hit[0] < CACHE_SEC:
        return hit[1]
    p = load_scan(cloud_owner(), mode)
    cache[mode] = (time.time(), p)
    return p


def _load(payload):
    """按鈕的 callback（在重畫前執行，所以可以改 widget 的值）。"""
    ss = st.session_state
    ss["result"] = payload_to_result(payload)
    ss.pop("scan_cache", None)                       # 沒有原始資料可重新評估，避免用舊資料算出別的結果
    ss["_result_mode"] = payload.get("mode", "breakout")
    ss["_result_scope"] = None                       # None = 不要因為範圍不同而自動重掃
    ss["_result_scope_label"] = "排程掃描"
    ss["_result_reuse"] = {}
    ss["_result_partial"] = True
    ss["_job_loaded_at"] = payload.get("at")
    ss["last_scan_at"] = _fmt_at(payload.get("at"))


def scheduled_panel():
    """一行：最新的排程結果 + 載入按鈕。沒有雲端、還沒跑過就什麼都不畫（設定說明在 background_panel）。"""
    if not (store.is_enabled() and cloud_owner()):
        return
    mode = st.session_state.get("strategy_mode", "breakout")
    p = _payload(mode)
    if not p:
        return
    n_go = next((int(r.get("進場檔數", 0)) for r in p.get("summary", [])), 0)
    n_watch = next((int(r.get("觀察檔數", 0)) for r in p.get("summary", [])), 0)
    same = st.session_state.get("_job_loaded_at") == p.get("at") and "result" in st.session_state
    c1, c2 = st.columns([4, 1.2], vertical_alignment="center")
    c1.caption(f"排程掃描 {_fmt_at(p.get('at'))} · {MODE_LABELS.get(mode, mode)} · {n_go} 檔進場、{n_watch} 檔觀察"
               + ("　（目前顯示的就是這份）" if same else ""))
    c2.button("載入這份結果", key=f"job_load_{mode}", disabled=same, use_container_width=True,
              on_click=_load, args=(p,))


def background_panel(sb):
    """自動排程的設定說明（手動掃描本身就在背景執行，不需要另外的按鈕）。"""
    with st.expander("自動排程設定", expanded=False):
        st.markdown(SETUP)


def render_panels(sb):
    scheduled_panel()
    background_panel(sb)


__all__ = ["render_panels", "scheduled_panel", "background_panel", "scan_key"]
