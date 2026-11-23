"""
跨頁面共用的動作（今日決策與找標的都能按「開始掃描」）。

用 st.status 顯示進度：執行中展開、完成後收成一行，不在結果上方殘留進度條。
"""
import logging
import tempfile
import time

import pandas as pd
import streamlit as st

from twscanner.core.tz import now_tw, today_tw
from twscanner.data.prices import load_stock_list
from twscanner.services import JobRunner, run_pool_scan, run_scan
from twscanner.services.scan import split_by_pool
from twscanner.storage.history import cleanup_old, save_scan
from twscanner.ui.scan_controls import scope_key, scope_label
from twscanner.ui.settings import build_cfg
from twscanner.ui.state import current_pool, get_journal, get_universe_items, save_pool, set_journal

log = logging.getLogger(__name__)


def scope_items(sb, cfg):
    """目前範圍要掃哪些股票 → [{code, company_name}]；上傳清單沒選檔回 None。"""
    if sb.mode == "掃描全台股":
        return get_universe_items(sb.universe_kind)
    if not sb.uploaded:
        return None
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(sb.uploaded.getvalue())
    return load_stock_list(tmp.name, cfg["etf_fix_map"])


def pool_coverage(sb):
    """(範圍內股票數, 需要下載的檔數)；範圍讀不到時回 None。給「換範圍」提示用。"""
    try:
        items = scope_items(sb, build_cfg())
    except Exception:
        return None
    if not items:
        return None
    _, missing = split_by_pool(current_pool(), items)
    return len(items), len(missing)


def _pool_age_min():
    p = st.session_state.get("data_pool") or {}
    try:
        h, m = map(int, str(p.get("at", "")).split(":"))
    except ValueError:
        return None
    now = now_tw()
    return (now.hour * 60 + now.minute) - (h * 60 + m)


@st.cache_resource
def scan_runner():
    """整個 App 共用一個背景執行器：掃描在伺服器的執行緒裡跑，換頁、重畫都不會中斷。"""
    return JobRunner()


def scan_running():
    return scan_runner().running()


def _scan_inputs(sb, fresh_prices):
    """在主執行緒把掃描需要的東西準備好（執行緒裡不能碰 session_state）。失敗回 (None, 訊息)。"""
    cfg = build_cfg()
    try:
        items = scope_items(sb, cfg)
    except Exception as e:
        return None, f"讀取股票清單失敗：{e}"
    if not items:
        return None, "請先在「找標的」上方的範圍上傳清單，或改選「全台股」"
    pool, age = current_pool(), _pool_age_min()
    meta = {"cfg": cfg, "scope_key": scope_key(sb), "scope_label": scope_label(sb),
            "mode": st.session_state.get("strategy_mode", "breakout"), "after_mode": sb.mode}
    return (lambda cb=None: run_pool_scan(cfg, items, pool, age, fresh_prices, cb)), meta


def start_scan(sb, fresh_prices=True):
    """
    按「開始掃描」：在背景開始，馬上回來。換頁、重新整理都不會中斷；完成後由 apply_finished_scan 自動載入。
    今天的資料池已經涵蓋範圍時只要幾秒，也一樣走這條路，行為一致。
    """
    run, meta = _scan_inputs(sb, fresh_prices)
    if run is None:
        st.error(meta)
        return False
    jid = scan_runner().start(f"掃描 {meta['scope_label']}", lambda cb: run(cb), meta=meta)
    if jid is None:
        st.toast("已經有一個掃描在進行中，完成後會自動載入")
        return False
    st.session_state["_scan_job_id"] = jid
    st.session_state.pop("_scan_error", None)
    return True


def execute_scan(sb, fresh_prices=False):
    """前景重算（只用今天已下載的資料、幾秒內完成）：換範圍時自動用。需要下載的一律走 start_scan。"""
    run, meta = _scan_inputs(sb, fresh_prices)
    if run is None:
        st.error(meta)
        return False
    with st.spinner("用今天已下載的資料重新計算 …"):
        try:
            out = run()
        except Exception as e:
            st.error(f"掃描失敗：{e}")
            return False
    _apply_scan(out, meta)
    return True


def _apply_scan(out, meta):
    """把掃描結果寫進這個 session（只能在主執行緒呼叫）。"""
    ss, result = st.session_state, out["result"]
    if out["pool_changed"]:
        save_pool(out["pool"], now_tw().strftime("%H:%M"))
    ss["result"] = result
    ss["_result_partial"] = False
    ss["scan_cache"] = result.get("scan_cache")
    ss["cfg"] = meta["cfg"]
    ss["_result_mode"] = meta["mode"]
    ss["_result_scope"] = meta["scope_key"]
    ss["_result_scope_label"] = meta["scope_label"]
    ss["_result_reuse"] = {"total": out["total"], "reused": out["reused"], "downloaded": out["downloaded"],
                           "data_at": (ss.get("data_pool") or {}).get("at")}
    ss["last_scan_at"] = now_tw().strftime("%m/%d %H:%M")
    _after_scan(result, meta["after_mode"])
    n = len(result["df"]) if result.get("df") is not None else 0
    how = f"，{out['reused']} 檔用已下載的資料" if out["reused"] else ""
    st.toast(f"掃描完成：{n} 檔{how}（{result['elapsed_sec']:.0f} 秒）")


def apply_finished_scan():
    """每次頁面執行開頭呼叫：這個 session 啟動的掃描完成了，就把結果載入。"""
    ss, r = st.session_state, scan_runner()
    snap = r.snapshot()
    jid = ss.get("_scan_job_id")
    if not jid or snap["id"] != jid or ss.get("_scan_job_applied") == jid:
        return
    if snap["state"] == "done" and snap["result"] is not None:
        try:
            _apply_scan(snap["result"], snap["meta"])
        except Exception as e:
            ss["_scan_error"] = f"掃描完成，但載入結果失敗：{e}"
        ss["_scan_job_applied"] = jid
        r.release(jid)
    elif snap["state"] == "error":
        ss["_scan_error"] = f"掃描失敗：{snap['error']}"
        ss["_scan_job_applied"] = jid


def _banner_poll():
    snap = scan_runner().snapshot()
    meta = snap.get("meta") or {}
    sec = int(time.time() - (snap["started"] or time.time()))
    st.progress(snap["pct"], text=f"背景掃描中 · {meta.get('scope_label', '')} · {snap['msg']}（{sec} 秒，可以切換頁面）")
    if snap["state"] != "running":
        st.rerun()                                   # 整頁重畫：apply_finished_scan 載入結果、橫幅消失


_banner_live = st.fragment(run_every=2)(_banner_poll)


def _adopt_job(jid):
    st.session_state["_scan_job_id"] = jid
    st.session_state.pop("_scan_job_applied", None)


def render_scan_banner():
    """所有頁面最上方：掃描進度、失敗訊息，或別個視窗啟動的掃描結果。"""
    ss, r = st.session_state, scan_runner()
    snap = r.snapshot()
    if snap["state"] == "running":
        _banner_live()
        return
    if ss.get("_scan_error"):
        c1, c2 = st.columns([6, 1], vertical_alignment="center")
        c1.error(ss["_scan_error"])
        if c2.button("關閉", key="scan_err_close"):
            ss.pop("_scan_error", None)
            st.rerun()
    elif snap["state"] == "done" and snap["result"] is not None and ss.get("_scan_job_id") != snap["id"]:
        c1, c2 = st.columns([4, 1.4], vertical_alignment="center")
        c1.caption(f"有一份剛完成的背景掃描（{(snap.get('meta') or {}).get('scope_label', '')}），不是這個視窗啟動的。")
        c2.button("載入結果", key="scan_adopt", on_click=_adopt_job, args=(snap["id"],), use_container_width=True)


def _after_scan(result, mode):
    """存歷史 + 記錄進場訊號到實戰日誌（失敗不影響掃描）。"""
    try:
        save_scan(result, market_state=result.get("market_state"), label=mode)
        cleanup_old(keep_n=30)
    except Exception as e:
        log.warning("存歷史失敗：%s", e)
    try:
        from twscanner.portfolio.journal import append_signals
        records, added = append_signals(get_journal(), result["df"], today_tw().isoformat(), mode=mode,
                                        signals=("進場",))
        if added:
            set_journal(records)          # 登入時由雲端同步上傳；不寫伺服器檔案
            st.toast(f"已記錄 {added} 筆進場訊號到實戰日誌")
    except Exception as e:
        log.warning("訊號日誌記錄失敗：%s", e)


def rescan_with_cache(toast=None):
    """用現有資料重新分析（換策略模式 / 風格 / 權重後，免重抓）。"""
    cache = st.session_state.get("scan_cache")
    if not cache:
        return False
    cfg = build_cfg()
    new_result = run_scan(cfg=cfg, cached=cache)
    new_result["scan_cache"] = cache
    st.session_state["result"] = new_result
    st.session_state["cfg"] = cfg
    st.session_state["_result_mode"] = st.session_state.get("strategy_mode", "breakout")
    if toast:
        st.toast(toast)
    return True


def sync_strategy_mode(mode_labels):
    """切換策略模式 → 自動用快取重算。"""
    cur = st.session_state.get("strategy_mode", "breakout")
    if st.session_state.get("scan_cache") and st.session_state.get("_result_mode") not in (None, cur):
        try:
            with st.spinner(f"切換為「{mode_labels.get(cur, cur)}」，用現有資料重算 …"):
                rescan_with_cache()
            st.rerun()
        except Exception as e:
            st.session_state["_result_mode"] = cur
            st.error(f"切換策略模式失敗：{e}")


def holdings_signature(df):
    """持股內容的指紋（只看有代號的列）：持股改了才需要重新分析；今日決策與持股頁共用。"""
    if df is None or not len(df):
        return ""
    cols = [c for c in ("股票代號", "公司名稱", "成本價", "持有股數") if c in df.columns]
    v = df.dropna(subset=["股票代號"]) if "股票代號" in df.columns else df
    v = v[v["股票代號"].astype(str).str.strip() != ""] if "股票代號" in v.columns else v
    return v[cols].astype(str).to_json() if len(v) else ""


def analyze_holdings(holdings_df):
    """持股編輯表 → 出場建議（持股頁與今日決策共用）。沒填進場日由引擎統一推估。"""
    from twscanner.data.prices import fix_stock_code
    from twscanner.services import run_holdings_scan

    if holdings_df is None or holdings_df.empty:
        return False
    cfg = build_cfg()
    valid = holdings_df.dropna(subset=["股票代號"])
    valid = valid[valid["股票代號"].astype(str).str.strip() != ""]
    items = []
    for _, row in valid.iterrows():
        code = fix_stock_code(row["股票代號"], cfg["etf_fix_map"])
        if code is None:
            continue
        items.append({
            "code": code, "company_name": str(row.get("公司名稱") or "").strip(),
            "entry_price": float(row["成本價"]) if pd.notna(row.get("成本價")) else 0.0,
            "entry_date": None,
            "shares": int(row["持有股數"]) if pd.notna(row.get("持有股數")) else None,
        })
    if not items:
        return False
    with st.status("分析持股中 …", expanded=False) as status:
        try:
            res = run_holdings_scan(cfg=cfg, holdings=items,
                                    progress_cb=lambda s, p, m: status.update(label=f"{s}：{m}"))
        except Exception as e:
            status.update(label=f"持股分析失敗：{e}", state="error")
            return False
        st.session_state["holdings_result"] = res
        st.session_state["holdings_analyzed_at"] = now_tw().strftime("%m/%d %H:%M")
        st.session_state["_hold_analyzed_sig"] = holdings_signature(holdings_df)
        status.update(label=f"持股分析完成：{len(items)} 檔", state="complete")
    return True
