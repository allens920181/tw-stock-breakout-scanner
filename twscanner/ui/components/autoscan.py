"""
背景掃描與排程結果（找標的頁、今日決策頁共用）。

- 排程：GitHub Actions 每個交易日收盤後掃描，把進場與觀察名單存到雲端；這裡讀回最新一份，不必等掃描。
- 背景：按下後在伺服器上另開一條執行緒掃描，離開這一頁也會繼續；完成後按「載入結果」。
兩者都需要雲端資料庫才能跨裝置；沒有雲端時，背景掃描的結果只留在伺服器記憶體裡（這個 App 重啟就沒了）。
"""
import time

import streamlit as st

from twscanner.core.tz import now_tw
from twscanner.services.jobs import (
    MODE_LABELS,
    JobRunner,
    load_scan,
    payload_to_result,
    run_scan_job,
    scan_key,
)
from twscanner.storage import cloud as store
from twscanner.ui.state import cloud_owner, get_base_config
from twscanner.ui.sync import SETTING_KEYS

CACHE_SEC = 60
SETUP = """**設定自動排程（只要做一次，約 5 分鐘）**

1. 需要先有雲端資料庫（設定頁 → 雲端帳號，說明在 `docs/雲端設定.md`）。
2. 到 GitHub 這個 repo → **Settings → Secrets and variables → Actions → New repository secret**，
   名稱填 `DATABASE_URL`，內容貼和 Streamlit Secrets 同一條 Neon 連線字串。
3. 到 **Actions → 排程掃描 → Run workflow** 手動跑一次確認成功（全台股約 10–15 分鐘）。
4. 之後每個交易日台灣時間 15:40 自動執行。要改時間，編輯 `.github/workflows/scheduled-scan.yml` 裡的 `cron`（UTC，台灣 = UTC+8）。

排程會同時算好三種策略與實證規則名單；執行失敗時 Actions 頁會顯示紅色叉叉（GitHub 預設也會寄通知信）。"""


@st.cache_resource
def runner():
    """整個 App 共用一個背景執行器（同一時間只跑一個掃描）。"""
    return JobRunner()


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


def _start(sb):
    """在主執行緒把需要的設定複製出來，再交給背景執行緒（執行緒裡不碰 session_state）。"""
    ss = st.session_state
    prefs = {k: ss[k] for k in SETTING_KEYS if k in ss}
    modes = [ss.get("strategy_mode", "breakout")] + [m for m in MODE_LABELS if m != ss.get("strategy_mode")]
    base, kind = get_base_config(), sb.universe_kind
    save = store.is_enabled() and bool(cloud_owner())
    owner = cloud_owner() or "me"
    runner().start("背景掃描", lambda cb: run_scan_job(base, prefs, kind, modes, owner, with_rulebook=False,
                                                       progress_cb=cb, save=save))


def _poll():
    snap = runner().snapshot()
    st.progress(snap["pct"], text=f"{snap['msg']}（已跑 {int(time.time() - (snap['started'] or time.time()))} 秒）")
    if snap["state"] != "running":
        st.rerun()                                   # 完成 → 整頁重畫，換成「載入結果」


_poll_live = st.fragment(run_every=2)(_poll)


def _load_done(mode):
    snap = runner().snapshot()
    res = snap.get("result") or {}
    p = res.get(mode) or next((v for k, v in res.items() if k in MODE_LABELS), None)
    if p:
        _load(p)


def background_panel(sb):
    """背景掃描（全台股範圍）。按下去可以離開這頁，回來看進度。"""
    ss = st.session_state
    r = runner()
    snap = r.snapshot()
    with st.expander("背景掃描與自動排程", expanded=snap["state"] == "running"):
        if snap["state"] == "running":
            _poll_live()
            return
        if snap["state"] == "error":
            st.error(f"上次背景掃描失敗：{snap['error']}")
        elif snap["state"] == "done":
            mode = ss.get("strategy_mode", "breakout")
            took = int((snap["finished"] or 0) - (snap["started"] or 0))
            st.success(f"背景掃描完成（{took} 秒），三種策略都算好了。")
            st.button(f"載入「{MODE_LABELS.get(mode, mode)}」結果", type="primary", key="job_load_done",
                      on_click=_load_done, args=(mode,))
        can = sb.mode == "掃描全台股"
        c1, c2 = st.columns([1.3, 3], vertical_alignment="center")
        if c1.button("在背景掃描", key="job_start", disabled=not can, use_container_width=True):
            _start(sb)
            st.rerun()
        c2.caption("按下後可以離開這一頁，回來再看。會一次算好三種策略。" if can
                   else "背景掃描只支援「全台股」範圍；上傳清單請用「開始掃描」。")
        st.caption("結果存在雲端（有登入時），換手機或電腦也看得到；沒有雲端時只留在這個 App 的記憶體，App 重啟就沒了。")
        st.markdown(SETUP)


def render_panels(sb):
    scheduled_panel()
    background_panel(sb)


__all__ = ["render_panels", "scheduled_panel", "background_panel", "scan_key"]
