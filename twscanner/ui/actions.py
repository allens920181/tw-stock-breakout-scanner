"""
跨頁面共用的動作（今日決策與找標的都能按「開始掃描」）。

用 st.status 顯示進度：執行中展開、完成後收成一行，不在結果上方殘留進度條。
"""
import logging
import tempfile

import pandas as pd
import streamlit as st

from twscanner.core.tz import now_tw, today_tw
from twscanner.data.prices import load_stock_list
from twscanner.services import run_scan
from twscanner.services.scan import merge_pool, refresh_prices, split_by_pool
from twscanner.storage.history import cleanup_old, save_scan
from twscanner.ui.scan_controls import scope_key, scope_label
from twscanner.ui.settings import build_cfg
from twscanner.ui.state import current_pool, get_journal, get_universe_items, save_pool, set_journal

log = logging.getLogger(__name__)


class _ListHandler(logging.Handler):
    def __init__(self, buf):
        super().__init__()
        self.buf = buf

    def emit(self, record):
        self.buf.append(self.format(record))


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


PRICE_STALE_MIN = 20     # 按「開始掃描」時，資料池的現價超過這麼久就重抓現價


def _pool_age_min():
    p = st.session_state.get("data_pool") or {}
    try:
        h, m = map(int, str(p.get("at", "")).split(":"))
    except ValueError:
        return None
    now = now_tw()
    return (now.hour * 60 + now.minute) - (h * 60 + m)


def execute_scan(sb, fresh_prices=True):
    """
    依目前範圍掃描，結果寫入 session_state。回傳是否成功。
    今天已經下載過的股票直接用資料池（只補抓缺的）：先掃全台股，之後換「僅普通股」或上傳清單都不必重抓。
    fresh_prices：使用者按下「開始掃描」時為 True — 沿用的資料若現價已舊（> 20 分鐘）就重抓現價；
    換範圍自動重算時為 False，直接用池子裡的資料。
    """
    with st.status("掃描準備中 …", expanded=True) as status:
        cfg = build_cfg()
        try:
            status.update(label="讀取範圍內的股票清單 …")
            items = scope_items(sb, cfg)
        except Exception as e:
            status.update(label=f"讀取股票清單失敗：{e}", state="error")
            return False
        if not items:
            status.update(label="請先在「找標的」上方的範圍上傳清單，或改選「全台股」", state="error")
            return False

        pool = current_pool()
        sub, missing = split_by_pool(pool, items)
        reused = len(items) - len(missing)
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
            if missing:
                if reused:
                    st.caption(f"範圍 {len(items)} 檔：{reused} 檔用今天已下載的資料，只下載 {len(missing)} 檔。")
                part = run_scan(cfg=cfg, progress_cb=on_progress, items=missing)
                pool = merge_pool(pool, part["scan_cache"])
                save_pool(pool, now_tw().strftime("%H:%M"))
                if reused:
                    sub, _ = split_by_pool(pool, items)
                    result = run_scan(cfg=cfg, cached=sub, progress_cb=on_progress)
                else:
                    result = part
            else:
                age = _pool_age_min()
                if fresh_prices and (age is None or age > PRICE_STALE_MIN):
                    status.update(label=f"更新 {len(sub['resolved'])} 檔現價（其他資料沿用今天已下載的）…")
                    pool["price_map"] = {**pool.get("price_map", {}), **refresh_prices(sub, cfg)}
                    save_pool(pool, now_tw().strftime("%H:%M"))
                    sub, _ = split_by_pool(pool, items)
                result = run_scan(cfg=cfg, cached=sub, progress_cb=on_progress)
        except Exception as e:
            status.update(label=f"掃描失敗：{e}", state="error")
            st.exception(e)
            return False
        finally:
            logging.getLogger().removeHandler(handler)

        st.session_state["result"] = result
        st.session_state["_result_partial"] = False
        st.session_state["scan_cache"] = result.get("scan_cache")
        st.session_state["cfg"] = cfg
        st.session_state["_result_mode"] = st.session_state.get("strategy_mode", "breakout")
        st.session_state["_result_scope"] = scope_key(sb)
        st.session_state["_result_scope_label"] = scope_label(sb)
        st.session_state["_result_reuse"] = {"total": len(items), "reused": reused, "downloaded": len(missing),
                                             "data_at": (st.session_state.get("data_pool") or {}).get("at")}
        st.session_state["last_scan_at"] = now_tw().strftime("%m/%d %H:%M")
        _after_scan(result, sb.mode)
        n = len(result["df"]) if result.get("df") is not None else 0
        how = f"，{reused} 檔用已下載的資料" if reused else ""
        status.update(label=f"掃描完成：{n} 檔，{result['elapsed_sec']:.0f} 秒{how}",
                      state="complete", expanded=False)
    st.toast(f"掃描完成：{n} 檔{how}")
    return True


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
