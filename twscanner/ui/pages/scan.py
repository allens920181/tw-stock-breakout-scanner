"""找標的：結論 → 數字 → 結果表（點一列看理由與交易計畫）→ 進階工具。"""
import io
from datetime import datetime

import pandas as pd
import streamlit as st

from twscanner.core.tz import today_tw
from twscanner.reporting.excel import write_excel
from twscanner.services import run_adaptive_recommend
from twscanner.services.today import CONDITION_KEYS, trade_plan
from twscanner.ui.actions import execute_scan, rescan_with_cache, sync_strategy_mode
from twscanner.ui.components.blocks import asof, buy_form, conclusion, empty, kpi_row, plan_card
from twscanner.ui.format import clean_stock_col, colors
from twscanner.ui.settings import build_cfg
from twscanner.ui.state import get_base_config, persist_calibration_date

SIGNAL_RANK = {"進場": 0, "觀察": 1, "不操作": 2, "未通過過濾": 3}
GROUPS = {
    "進場計畫": ["股票", "綜合評級", "訊號判斷", "評分", "說明", "進場參考價", "停損價",
               "目標價1(+1R半倉)", "目標價2(+2R出清)", "建議張數"],
    "風險與部位": ["股票", "訊號判斷", "風險%", "RR比", "建議張數", "進場成本", "佔資金%",
                "現價偏離%", "乖離MA20%", "部位提示"],
    "籌碼與基本面": ["股票", "訊號判斷", "籌碼確認", "法人買賣超(張)", "外資買賣超(張)", "法人連買天數",
                 "法人5日累計(張)", "融資券提示", "營收動能", "月營收YoY%", "距財報日"],
    "技術面": ["股票", "訊號判斷", "收盤價", "換手率%", "相對強度RS%", "ADX", "K", "D", "MA20", "MA60",
            "啟動就緒度"],
}
NUM_FMT = {
    "進場參考價": "%.2f", "停損價": "%.2f", "目標價1(+1R半倉)": "%.2f", "目標價2(+2R出清)": "%.2f",
    "收盤價": "%.2f", "MA20": "%.2f", "MA60": "%.2f", "K": "%.1f", "D": "%.1f", "ADX": "%.1f",
    "風險%": "%.2f%%", "佔資金%": "%.2f%%", "現價偏離%": "%+.2f%%", "乖離MA20%": "%+.2f%%",
    "換手率%": "%.2f%%", "相對強度RS%": "%+.2f%%", "月營收YoY%": "%+.1f%%", "RR比": "%.2f",
    "建議張數": "%d 張", "進場成本": "localized", "法人買賣超(張)": "localized",
    "外資買賣超(張)": "localized", "法人5日累計(張)": "localized", "法人連買天數": "%d 天", "評分": "%d",
}
SIGNED = ["法人買賣超(張)", "外資買賣超(張)", "法人5日累計(張)", "相對強度RS%", "月營收YoY%",
          "現價偏離%", "乖離MA20%"]


def _headline(df, market_state):
    n_go = int((df["訊號判斷"] == "進場").sum()) if "訊號判斷" in df else 0
    n_watch = int((df["訊號判斷"] == "觀察").sum()) if "訊號判斷" in df else 0
    regime = (market_state or {}).get("regime")
    if regime == "bear":
        return (f"大盤空頭：系統暫停進場（{n_watch} 檔列為觀察）",
                "只做多的策略在空頭時休息。可以先把觀察名單記下來，等大盤翻多再看。", "stop")
    if n_go == 0:
        return (f"今天沒有達到進場標準的股票（{n_watch} 檔觀察）",
                "沒有好機會時不做，也是一種操作。", "wait")
    return (f"{n_go} 檔達到進場標準，{n_watch} 檔觀察",
            "點表格中的一列，看入選理由與完整交易計畫。挑 1–2 檔就好。", "go")


def _style(view):
    c = colors()

    def sig(v):
        if v == "進場":
            return f"background-color:{c['up_bg']};color:{c['up_text']};font-weight:600"
        if v == "觀察":
            return "color:#1D4ED8"
        return "color:#64748B"

    def signed(v):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return ""
        return f"color:{c['up'] if f > 0 else c['down']}" if f else ""
    sty = view.style
    if "訊號判斷" in view:
        sty = sty.map(sig, subset=["訊號判斷"])
    cols = [x for x in SIGNED if x in view.columns]
    if cols:
        sty = sty.map(signed, subset=cols)
    return sty


def _table(df):
    f1, f2, f3 = st.columns([1.6, 2.6, 1.4])
    sig = f1.segmented_control("訊號", ["全部", "進場", "觀察"], default="全部", key="scan_sig")
    group = f2.segmented_control("欄位", list(GROUPS) + ["全部欄位"], default="進場計畫", key="scan_grp")
    kw = f3.text_input("搜尋", placeholder="代號或名稱", key="scan_kw", label_visibility="collapsed")

    d = df.copy()
    d["_rank"] = d["訊號判斷"].map(SIGNAL_RANK).fillna(3) if "訊號判斷" in d else 0
    by = ["_rank", "評分"] if "評分" in d else ["_rank"]
    d = d.sort_values(by, ascending=[True, False][:len(by)])
    if sig in ("進場", "觀察"):
        d = d[d["訊號判斷"] == sig]
    if kw:
        k = kw.strip()
        d = d[d["股票"].astype(str).str.contains(k, regex=False) | d.get("公司名稱", pd.Series("", index=d.index))
              .astype(str).str.contains(k, regex=False)]
    d = d.reset_index(drop=True)
    # 「無法分析」多半是沒通過品質過濾（例如未站上 MA60），把原因直接顯示出來
    if "訊號判斷" in d:
        filtered = d["訊號判斷"] == "無法分析"
        d.loc[filtered, "訊號判斷"] = "未通過過濾"
        reason = d["狀態"] if "狀態" in d else pd.Series("", index=d.index)
        action = d["操作建議"] if "操作建議" in d else pd.Series("", index=d.index)
        d["說明"] = reason.where(filtered, action)
    view = clean_stock_col(d)
    if group and group != "全部欄位":
        view = view[[c for c in GROUPS[group] if c in view.columns]]
    else:
        view = view.drop(columns=[c for c in view.columns if c.startswith("_")])
    if view.empty:
        empty("沒有符合條件的股票", "換一個訊號篩選或清除搜尋字。")
        return None
    for c in NUM_FMT:
        if c in view:
            view[c] = pd.to_numeric(view[c], errors="coerce")       # None → 空白，不顯示「None」
    for c in view.columns:
        if view[c].dtype == object:
            view[c] = view[c].where(view[c].notna() & (view[c].astype(str) != "None"), "—")
    cfg = {c: st.column_config.NumberColumn(c, format=f) for c, f in NUM_FMT.items() if c in view}
    cfg["股票"] = st.column_config.TextColumn("股票", pinned=True)
    event = st.dataframe(_style(view), hide_index=True, use_container_width=True,
                         height=min(36 * (len(view) + 1) + 4, 560), column_config=cfg,
                         on_select="rerun", selection_mode="single-row", key="scan_table")
    st.caption(f"共 {len(view)} 檔 · 依訊號、分數排序 · 點一列看理由與交易計畫")
    rows = event.selection.rows if event and event.selection else []
    return d.iloc[rows[0]] if rows else None


def stock_detail(row, key="scan"):
    """一列結果 → 條件逐項 + 交易計畫卡 + 我已買進。找標的與今日決策共用。"""
    plan = trade_plan(row)
    plan_card(plan)
    with st.expander("為什麼是這個分數：條件逐項", expanded=False):
        lines = []
        for k, label in CONDITION_KEYS:
            if k in row.index:
                v = row.get(k)
                ok = v is not None and v == v and bool(v)
                lines.append(f"- {'✓ 通過' if ok else '✗ 未通過'}　{label}")
        for k in ("評級理由", "籌碼確認", "營收動能", "融資券提示", "部位提示", "距財報日"):
            v = row.get(k)
            if v is not None and v == v and str(v) not in ("", "—"):
                lines.append(f"- **{k}**：{v}")
        st.markdown("\n".join(lines) or "沒有條件明細。")
    buy_form(plan, key)


def _advanced(result, df):
    base_cfg = get_base_config()
    with st.expander("進階：重新評估、自動校準、下載", expanded=False):
        c1, c2 = st.columns([3, 1.3])
        c1.caption("換了風格、權重或門檻後，可以用現有資料重新評估，不必重抓。")
        if c2.button("用現有資料重新評估", use_container_width=True):
            with st.spinner("重新分析中 …"):
                rescan_with_cache("已用現有資料重新評估")
            st.rerun()
        _calibration(result)
        st.divider()
        summary, failed = result["summary"], result["failed_df"]
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, sheet_name="全部分析結果", index=False)
            summary.to_excel(w, sheet_name="Report摘要", index=False)
            if failed is not None and len(failed):
                failed.to_excel(w, sheet_name="錯誤清單", index=False)
        d1, d2 = st.columns(2)
        d1.download_button("下載 Excel 報告", data=buf.getvalue(), file_name="台股分析報告.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
        if d2.button("寫入專案目錄", use_container_width=True):
            out = st.session_state.get("cfg", base_cfg)["output"]
            st.success(f"已輸出：{write_excel(df, summary, failed, out['dir'], out['prefix'])}")
        if failed is not None and len(failed):
            st.caption(f"抓不到資料的股票（{len(failed)} 檔）")
            st.dataframe(failed, use_container_width=True, hide_index=True)


def _calibration(result):
    res = st.session_state["scan_cache"].get("resolved", []) if st.session_state.get("scan_cache") else []
    if not res:
        return
    st.markdown("**自動校準**：用現有資料跑回測，只套用樣本外驗證通過的參數，再重新評估。")
    lc = st.session_state.get("last_calibrated_date")
    if lc:
        try:
            days = (today_tw() - datetime.fromisoformat(lc).date()).days
            st.caption(f"上次校準 {days} 天前" + ("。建議每月一次就好，太頻繁會過度擬合。" if days < 20 else "。"))
        except Exception:
            pass
    if len(res) > 400:
        st.caption(f"目前 {len(res)} 檔，校準可能要數分鐘。")
    o1, o2 = st.columns([2, 1])
    lookback = o1.slider("校準回測天數", 60, 250, int(st.session_state.get("ac_lookback", 120)), 30,
                         key="ac_lookback")
    if not o2.button("校準並重新評估", use_container_width=True):
        if st.session_state.get("autocal_plan"):
            p = st.session_state["autocal_plan"]
            st.caption(("已套用：" + "、".join(p["summary"])) if p["summary"] else "上次校準沒有可套用的建議。")
        return
    from twscanner.research.adaptive import pick_applicable
    bar = st.progress(0.0, text="自動校準中 …")
    try:
        ar = run_adaptive_recommend(res, build_cfg(), lookback_days=int(lookback),
                                    hold_days=int(st.session_state.get("ac_hold", 10)),
                                    targets=("thresholds", "weights", "regime"),
                                    progress_cb=lambda p, m: bar.progress(min(p * 0.8, 0.8), text=m))
        plan = pick_applicable(ar, require_oos=True)
        ap = plan["applied"]
        for k in ("thr_enter", "f_atr_mult", "regime_thresholds"):
            if k in ap:
                st.session_state[k] = ap[k]
        keymap = {"breakout_with_volume": "w_breakout", "ma_bullish": "w_ma", "turnover_strong": "w_turnover",
                  "kd": "w_kd", "macd": "w_macd", "rel_strength": "w_rs", "trend_confirm": "w_trend"}
        for sk, ssk in keymap.items():
            if sk in ap.get("weights", {}):
                st.session_state[ssk] = ap["weights"][sk]
        st.session_state["adapt_result"] = ar
        st.session_state["autocal_plan"] = plan
        persist_calibration_date()
        rescan_with_cache()
        st.rerun()
    except Exception as e:
        st.error(f"自動校準失敗：{e}")


def render(sb):
    if sb.run_btn and execute_scan(sb):
        st.rerun()      # 今日決策分頁在前面已畫完，重跑讓它看到新的掃描結果
    sync_strategy_mode(sb.mode_labels)

    if "result" not in st.session_state:
        conclusion("還沒有掃描結果",
                   "三步驟：① 側欄選資料來源（上傳清單或全台股）與策略模式 → ② 按「開始掃描」"
                   "→ ③ 點結果表的一列，看入選理由與交易計畫；買進後按「我已買進」記入持股。", "info")
        if st.button("用目前設定開始掃描", type="primary"):
            execute_scan(sb)
            st.rerun()
        return

    result = st.session_state["result"]
    df = result["df"]
    market_state = result.get("market_state")
    lead, sub, tone = _headline(df, market_state)
    conclusion(lead, sub, tone)
    s = result["summary"].iloc[0]
    mode_name = sb.mode_labels.get(st.session_state.get("_result_mode", "breakout"), "")
    asof(f"資料截至 {st.session_state.get('last_scan_at', '')} · 策略：{mode_name} · "
         f"掃描 {int(s.get('掃描股票數', 0))} 檔 · 耗時 {s.get('執行秒數', '—')} 秒")
    kpi_row([
        ("達進場標準", f"{int(s.get('進場檔數', 0))}", "挑 1–2 檔"),
        ("觀察", f"{int(s.get('觀察檔數', 0))}", "條件差一點"),
        ("不操作 / 未通過過濾", f"{int(len(df) - s.get('進場檔數', 0) - s.get('觀察檔數', 0))}",
         f"其中 {int((df['訊號判斷'] == '無法分析').sum())} 檔沒通過品質過濾" if "訊號判斷" in df else None),
        ("大盤", (market_state or {}).get("label", "—").replace("🟢", "").replace("🔴", "")
         .replace("🟡", "").strip() or "—", None),
    ])
    st.markdown("### 結果")
    picked = _table(df)
    if picked is not None:
        st.markdown("### 交易計畫")
        stock_detail(picked, key=f"scan_{picked.get('股票')}")
    _advanced(result, df)
