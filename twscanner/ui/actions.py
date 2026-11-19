"""
跨頁面共用的動作（今日決策與找標的都能按「開始掃描」）。

用 st.status 顯示進度：執行中展開、完成後收成一行，不在結果上方殘留進度條。
"""
import logging
import tempfile

import pandas as pd
import streamlit as st

from twscanner.core.tz import now_tw, today_tw
from twscanner.data.universe import fetch_twse_universe
from twscanner.services import run_scan
from twscanner.storage import cloud as store
from twscanner.storage.history import cleanup_old, save_scan
from twscanner.ui.settings import build_cfg
from twscanner.ui.state import cloud_owner

log = logging.getLogger(__name__)


class _ListHandler(logging.Handler):
    def __init__(self, buf):
        super().__init__()
        self.buf = buf

    def emit(self, record):
        self.buf.append(self.format(record))


def execute_scan(sb):
    """依側欄的資料來源執行掃描，結果寫入 session_state。回傳是否成功。"""
    items, input_path = None, None
    with st.status("掃描準備中 …", expanded=True) as status:
        if sb.mode == "掃描全台股":
            try:
                status.update(label="抓取全台股清單 …")
                raw = fetch_twse_universe(
                    include_common=sb.universe_kind in ("twse", "twse-common"),
                    include_etf=sb.universe_kind in ("twse", "twse-etf"))
                items = [{"code": x["code"], "company_name": x["company_name"]} for x in raw]
            except Exception as e:
                status.update(label=f"抓取全台股清單失敗：{e}", state="error")
                return False
        elif sb.uploaded:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            tmp.write(sb.uploaded.getvalue())
            tmp.close()
            input_path = tmp.name
        else:
            status.update(label="請先在側欄上傳清單，或改選「全台股」", state="error")
            return False

        cfg = build_cfg()
        buf = []
        handler = _ListHandler(buf)
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))
        logging.getLogger().setLevel(logging.INFO)
        logging.getLogger().addHandler(handler)
        bar = st.progress(0.0)
        log_box = st.empty()

        def on_progress(stage, pct, msg):
            status.update(label=f"{stage}：{msg}")
            bar.progress(min(pct, 1.0))
            log_box.caption("\n\n".join(buf[-4:]))

        try:
            result = run_scan(input_path=input_path, cfg=cfg, progress_cb=on_progress, items=items)
        except Exception as e:
            status.update(label=f"掃描失敗：{e}", state="error")
            st.exception(e)
            return False
        finally:
            logging.getLogger().removeHandler(handler)

        st.session_state["result"] = result
        st.session_state["scan_cache"] = result.get("scan_cache")
        st.session_state["cfg"] = cfg
        st.session_state["_result_mode"] = st.session_state.get("strategy_mode", "breakout")
        st.session_state["last_scan_at"] = now_tw().strftime("%m/%d %H:%M")
        _after_scan(result, sb.mode)
        n = len(result["df"]) if result.get("df") is not None else 0
        status.update(label=f"掃描完成：{n} 檔，{result['elapsed_sec']:.0f} 秒",
                      state="complete", expanded=False)
    st.toast(f"掃描完成：{n} 檔，{result['elapsed_sec']:.0f} 秒")
    return True


def _after_scan(result, mode):
    """存歷史 + 記錄進場訊號到實戰日誌（失敗不影響掃描）。"""
    try:
        save_scan(result, market_state=result.get("market_state"), label=mode)
        cleanup_old(keep_n=30)
    except Exception as e:
        log.warning("存歷史失敗：%s", e)
    try:
        from twscanner.portfolio.journal import load_journal, log_signals
        added = log_signals(result["df"], today_tw().isoformat(), mode=mode, signals=("進場",))
        if added:
            st.toast(f"已記錄 {added} 筆進場訊號到實戰日誌", icon="📓")
            if cloud_owner():
                store.save_journal(cloud_owner(), load_journal())
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
    """側欄切換策略模式 → 自動用快取重算。"""
    cur = st.session_state.get("strategy_mode", "breakout")
    if st.session_state.get("scan_cache") and st.session_state.get("_result_mode") not in (None, cur):
        try:
            with st.spinner(f"切換為「{mode_labels.get(cur, cur)}」，用現有資料重算 …"):
                rescan_with_cache()
            st.rerun()
        except Exception as e:
            st.session_state["_result_mode"] = cur
            st.error(f"切換策略模式失敗：{e}")


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
        status.update(label=f"持股分析完成：{len(items)} 檔", state="complete")
    return True
