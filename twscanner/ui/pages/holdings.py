"""💼 持股管理分頁。"""
import io
import logging

import pandas as pd
import streamlit as st

from twscanner.core.tz import now_tw, today_tw
from twscanner.data.names import lookup_names
from twscanner.data.prices import fix_stock_code
from twscanner.services import run_holdings_scan
from twscanner.storage import cloud as store
from twscanner.ui.components.common import make_holdings_template, make_progress_block
from twscanner.ui.glossary import HELP
from twscanner.ui.settings import build_cfg
from twscanner.ui.state import cloud_owner, get_base_config, get_code_name_map


def render():
    """💼 持股管理"""
    base_cfg = get_base_config()
    # ============ 初始化 ============
    if "holdings_df" not in st.session_state:
        st.session_state["holdings_df"] = pd.DataFrame([
            {"股票代號": "2330", "公司名稱": "台積電", "成本價": 0.00,
             "持有股數": 1000},
        ])

    # 正規化欄位：清掉任何來源殘留的舊欄位（進場日/進場價/持有張數），只留 4 個正規欄
    def _normalize_holdings(_df):
        _df = _df.copy()
        if "進場價" in _df.columns and "成本價" not in _df.columns:
            _df = _df.rename(columns={"進場價": "成本價"})
        if "持有張數" in _df.columns and "持有股數" not in _df.columns:
            _df["持有股數"] = pd.to_numeric(_df["持有張數"], errors="coerce") * 1000
        keep = ["股票代號", "公司名稱", "成本價", "持有股數"]
        for c in keep:
            if c not in _df.columns:
                _df[c] = None
        return _df[keep]

    _norm = _normalize_holdings(st.session_state["holdings_df"])
    if list(_norm.columns) != list(st.session_state["holdings_df"].columns):
        st.session_state["holdings_df"] = _norm   # 有殘留欄才覆寫，避免打斷編輯
        st.session_state["holdings_editor_version"] = (
            st.session_state.get("holdings_editor_version", 0) + 1)

    holdings_df_curr = st.session_state["holdings_df"]
    valid_h = holdings_df_curr.copy()
    if "股票代號" in valid_h.columns:
        valid_h = valid_h.dropna(subset=["股票代號"])
        valid_h = valid_h[valid_h["股票代號"].astype(str).str.strip() != ""]

    h_result = st.session_state.get("holdings_result")

    # ============ 統計：成本 / 現值 / 損益 ============
    total_cost = 0.0
    if len(valid_h) and "成本價" in valid_h.columns and "持有股數" in valid_h.columns:
        try:
            cost_series = (
                valid_h["成本價"].fillna(0).astype(float)
                * valid_h["持有股數"].fillna(0).astype(float)
            )
            total_cost = float(cost_series.sum())
        except Exception:
            total_cost = 0.0

    total_value = 0.0
    total_pnl = 0.0
    total_pnl_pct = 0.0
    if h_result and total_cost > 0:
        h_df_full = h_result["df"]
        code_to_current = {}
        for _, r in h_df_full.iterrows():
            stock_str = str(r.get("股票", ""))
            code = stock_str.split(".")[0]
            cur = r.get("目前價")
            if cur is not None and pd.notna(cur):
                code_to_current[code] = float(cur)
        for _, row in valid_h.iterrows():
            code = fix_stock_code(row["股票代號"], base_cfg.get("etf_fix_map", {}))
            if not code:
                continue
            cur = code_to_current.get(code)
            if cur is None:
                continue
            shares = row.get("持有股數")
            if shares is None or pd.isna(shares):
                continue
            total_value += cur * float(shares)
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    # ============ KPI 列 ============
    kc = st.columns(4)
    kc[0].metric("持股檔數", len(valid_h),
                   help="目前持有的股票數量")
    kc[1].metric("總成本", f"{int(total_cost):,}" if total_cost else "—",
                   help="所有持股的成本價 × 持有股數加總（元）")
    kc[2].metric("總現值", f"{int(total_value):,}" if total_value else "—",
                   help="所有持股的目前價 × 持有股數加總（元）。需先點「分析持股」")
    if total_cost > 0 and h_result:
        kc[3].metric("未實現損益", f"{int(total_pnl):+,}",
                       delta=f"{total_pnl_pct:+.2f}%",
                       delta_color="normal" if total_pnl >= 0 else "inverse",
                       help="總現值 - 總成本。delta 為損益百分比")
    else:
        kc[3].metric("未實現損益", "—",
                       help="需先點「分析持股」取得目前價才能計算")

    st.markdown("")

    # ============ 標題 + 工具列 ============
    th1, th2 = st.columns([5, 2])
    th1.markdown("### 持股清單")
    th1.caption("代號填了，公司名稱會自動帶入。儲存在瀏覽器 session — 刷新會清空，記得「匯出」備份。")

    with th2:
        tt = st.columns(4)
        if tt[0].button("清空", use_container_width=True):
            st.session_state["holdings_df"] = pd.DataFrame(columns=[
                "股票代號", "公司名稱", "成本價", "持有股數",
            ])
            st.session_state.pop("holdings_result", None)
            st.session_state["holdings_editor_version"] = (
                st.session_state.get("holdings_editor_version", 0) + 1
            )
            st.rerun()
        e_buf = io.BytesIO()
        with pd.ExcelWriter(e_buf, engine="openpyxl") as writer:
            st.session_state["holdings_df"].to_excel(writer, sheet_name="持股", index=False)
        e_buf.seek(0)
        tt[1].download_button(
            "匯出", data=e_buf.getvalue(),
            file_name="my_holdings.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        with tt[2].popover("上傳", use_container_width=True):
            uploaded_h = st.file_uploader(
                "上傳 xlsx 覆蓋", type=["xlsx"], key="holdings_uploader",
                label_visibility="collapsed",
            )
            if uploaded_h:
                try:
                    up_df = pd.read_excel(uploaded_h)
                    # 舊版欄名相容
                    if "進場價" in up_df.columns and "成本價" not in up_df.columns:
                        up_df = up_df.rename(columns={"進場價": "成本價"})
                    if "進場日" in up_df.columns:
                        up_df = up_df.drop(columns=["進場日"])
                    st.session_state["holdings_df"] = up_df
                    st.session_state["holdings_editor_version"] = (
                        st.session_state.get("holdings_editor_version", 0) + 1
                    )
                    st.success(f"已載入 {len(up_df)} 筆")
                except Exception as e:
                    st.error(f"讀取失敗：{e}")
        tt[3].download_button(
            "模板",
            data=make_holdings_template(),
            file_name="持股_模板.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    # ============ 編輯器（fragment 隔離 rerun，不在 render 中重設 data 源）============
    # editor_version 用來在「清空 / 上傳 / 查詢名稱」後重置編輯器
    if "holdings_editor_version" not in st.session_state:
        st.session_state["holdings_editor_version"] = 0

    @st.fragment
    def holdings_editor_fragment():
        editor_key = f"holdings_editor_v{st.session_state['holdings_editor_version']}"
        edited = st.data_editor(
            st.session_state["holdings_df"],
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "股票代號": st.column_config.TextColumn(
                    "股票代號", required=True, width="small",
                    help="例：2330",
                ),
                "公司名稱": st.column_config.TextColumn(
                    "公司名稱", width="medium",
                    help="留空後按「查詢名稱」會自動帶入",
                ),
                "成本價": st.column_config.NumberColumn(
                    "成本價", min_value=0.0, step=0.01, format="%.2f", width="small",
                    help=HELP["cost_price"],
                ),
                "持有股數": st.column_config.NumberColumn(
                    "持有股數", min_value=0, step=100, format="%d", width="small",
                    help=HELP["shares_held"],
                ),
            },
            key=editor_key,
        )

        # 鏡像當前內容到另一個 key 給外部讀（不動 holdings_df，避免打斷編輯）
        st.session_state["_holdings_edited"] = edited

        # ===== 查詢名稱按鈕 =====
        pending_codes = []
        if len(edited) and "股票代號" in edited.columns:
            for _, row in edited.iterrows():
                code_raw = row.get("股票代號")
                if code_raw is None or pd.isna(code_raw):
                    continue
                code = fix_stock_code(code_raw, base_cfg.get("etf_fix_map", {}))
                if not code:
                    continue
                current_name = row.get("公司名稱")
                if (current_name is None or pd.isna(current_name)
                        or str(current_name).strip() == ""):
                    pending_codes.append(code)
        pending = len(pending_codes)

        qb_col1, qb_col2 = st.columns([1.5, 5])
        label = f"查詢名稱 ({pending})" if pending else "查詢名稱"
        if qb_col1.button(label, use_container_width=True,
                           disabled=pending == 0,
                           help="TWSE 對照表 → 本地快取 → yfinance（首次較慢）"):
            twse_map = get_code_name_map()
            with st.spinner("查詢中（含 yfinance 後備）…"):
                found = lookup_names(pending_codes, twse_map)
            new_df = edited.copy()
            filled = 0
            for i, row in new_df.iterrows():
                code_raw = row.get("股票代號")
                if code_raw is None or pd.isna(code_raw):
                    continue
                code = fix_stock_code(code_raw, base_cfg.get("etf_fix_map", {}))
                if not code:
                    continue
                current_name = row.get("公司名稱")
                if (current_name is None or pd.isna(current_name)
                        or str(current_name).strip() == ""):
                    name = found.get(code)
                    if name:
                        new_df.at[i, "公司名稱"] = name
                        filled += 1
            st.session_state["holdings_df"] = new_df
            st.session_state["holdings_editor_version"] += 1  # 換 key 重置編輯器
            miss = pending - filled
            if miss:
                st.warning(f"已填 {filled} 檔，{miss} 檔仍查無 — 請手動輸入")
            else:
                st.success(f"已填入 {filled} 檔名稱")
            st.rerun(scope="fragment")
        if pending:
            qb_col2.caption(f"有 {pending} 檔代號填了但名稱空白，點左側按鈕查詢")
        else:
            qb_col2.caption("名稱填寫完成")

    holdings_editor_fragment()
    edited = st.session_state.get("_holdings_edited", st.session_state["holdings_df"])
    # 把當前編輯狀態鏡像回 holdings_df 給下游讀 KPI / 分析使用
    # （在 fragment 之外，不會影響編輯器的內部追蹤）
    st.session_state["holdings_df"] = edited
    # 雲端自動保存（僅內容變動時才寫，避免每次 rerun 都打 DB）
    if cloud_owner():
        try:
            _sig = edited.to_json()
            if st.session_state.get("_hold_sig") != _sig:
                if store.save_holdings(cloud_owner(), edited):
                    st.session_state["_hold_sig"] = _sig
        except Exception:
            pass

    # ============ 分析按鈕 ============
    st.markdown("")
    ac1, ac2 = st.columns([1.4, 5])
    do_analyze = ac1.button("分析持股", type="primary", use_container_width=True,
                              disabled=len(valid_h) == 0)
    last_analyzed = st.session_state.get("holdings_analyzed_at")
    if last_analyzed:
        ac2.caption(f"上次分析：{last_analyzed}")
    elif len(valid_h) == 0:
        ac2.caption("請先填入至少一檔持股")
    else:
        ac2.caption("分析會抓最新收盤價並判斷出場建議")

    if do_analyze:
        valid = edited.dropna(subset=["股票代號"])
        valid = valid[valid["股票代號"].astype(str).str.strip() != ""]
        cfg = build_cfg()
        holdings_list = []
        today = today_tw()
        for _, row in valid.iterrows():
            code = fix_stock_code(row["股票代號"], cfg["etf_fix_map"])
            if code is None:
                continue
            shares_val = int(row["持有股數"]) if pd.notna(row.get("持有股數")) else None
            holdings_list.append({
                "code": code,
                "company_name": str(row.get("公司名稱", "")).strip(),
                "entry_price": float(row["成本價"]) if pd.notna(row.get("成本價")) else 0,
                "entry_date": today,  # 無進場日欄位，預設今天（時間停損從今天起算）
                "shares": shares_val,
            })

        bar, log_area, buf, handler = make_progress_block("持股分析")
        logging.getLogger().addHandler(handler)

        def h_progress(stage, pct, msg):
            bar.progress(min(pct, 1.0), text=f"{stage} — {msg}")
            log_area.code("\n".join(buf[-30:]) or "（執行中…）")

        try:
            with st.spinner("分析中 …"):
                h_result_new = run_holdings_scan(
                    cfg=cfg, holdings=holdings_list, progress_cb=h_progress,
                )
            st.session_state["holdings_result"] = h_result_new
            st.session_state["holdings_analyzed_at"] = now_tw().strftime("%H:%M:%S")
        except Exception as e:
            st.error(f"分析失敗：{e}")
        finally:
            logging.getLogger().removeHandler(handler)
        bar.progress(1.0, text="完成")
        st.rerun()

    # ============ 分析結果 ============
    if "holdings_result" in st.session_state:
        h_df = st.session_state["holdings_result"]["df"].copy()
        if "操作建議" in h_df.columns:
            for sym in ["⛔", "🟢", "🔴", "🟡", "⌛", "✅", "❓", "⚠️"]:
                h_df["操作建議"] = h_df["操作建議"].astype(str).str.replace(sym, "")
            h_df["操作建議"] = h_df["操作建議"].str.strip()

        urgent_keywords = ["停損", "技術轉弱", "+2R", "+1R", "時間停損", "移動停利"]
        urgent = h_df[h_df["操作建議"].apply(
            lambda a: any(k in str(a) for k in urgent_keywords)
        )] if "操作建議" in h_df.columns else h_df.iloc[0:0]
        hold = h_df.drop(urgent.index) if len(urgent) else h_df

        st.divider()

        # ===== 今天行動摘要（一眼看懂今天要做什麼）=====
        qty_col = h_df.get("賣出量", pd.Series(dtype=str)).astype(str)
        n_sell = int(qty_col.str.contains("全出").sum())
        n_half = int(qty_col.str.contains("賣半").sum())
        n_hold = int(qty_col.str.contains("保留").sum())
        st.markdown(
            f"<div style='font-size:14px;margin-bottom:6px;'>📋 <b>今天</b>："
            f"<span style='color:#DC2626;font-weight:700;'>{n_sell} 檔要賣</span> · "
            f"<span style='color:#D97706;font-weight:700;'>{n_half} 檔減半</span> · "
            f"<span style='color:#059669;'>{n_hold} 檔續抱</span></div>",
            unsafe_allow_html=True,
        )

        # 優先顯示需要動作（紅色強調 banner）
        if len(urgent):
            st.markdown(
                f"<div class='holdings-alert'>"
                f"⚠ 有 <b>{len(urgent)}</b> 檔持股建議立即處理"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.dataframe(urgent, use_container_width=True, hide_index=True)
        else:
            st.markdown(
                "<div class='holdings-ok'>✓ 所有持股目前皆建議續抱</div>",
                unsafe_allow_html=True,
            )

        if len(hold):
            st.markdown("### 續抱")
            st.dataframe(hold, use_container_width=True, hide_index=True)

        # ============ 出場策略階梯 ============
        st.markdown("### 出場策略階梯")
        st.caption("每檔持股的完整出場規劃 — 觸發任一條件就執行對應動作")

        exit_cols = ["股票", "公司名稱", "成本價", "目前價", "報酬%",
                      "停損價", "目標1(+1R半倉)", "目標2(+2R出清)",
                      "移動停利MA10", "時間停損日", "技術轉弱觸發"]
        avail = [c for c in exit_cols if c in h_df.columns]
        exit_df = h_df[avail].copy()

        # 數值格式化 + help
        col_cfg_exit = {}
        exit_help = {
            "成本價": HELP["cost_price"],
            "目前價": HELP["current_price"],
            "停損價": HELP["stop_loss"],
            "目標1(+1R半倉)": HELP["target_1r"],
            "目標2(+2R出清)": HELP["target_2r"],
            "移動停利MA10": HELP["trail_stop_ma10"],
            "時間停損日": HELP["time_stop"],
            "技術轉弱觸發": HELP["tech_weak"],
        }
        for c in ["成本價", "目前價", "停損價", "目標1(+1R半倉)",
                   "目標2(+2R出清)", "移動停利MA10"]:
            if c in exit_df.columns:
                col_cfg_exit[c] = st.column_config.NumberColumn(
                    c, format="%.2f", help=exit_help.get(c),
                )
        if "報酬%" in exit_df.columns:
            col_cfg_exit["報酬%"] = st.column_config.NumberColumn(
                "報酬%", format="%.2f%%", help=HELP["profit_pct"],
            )
        for c in ["時間停損日", "技術轉弱觸發"]:
            if c in exit_df.columns:
                col_cfg_exit[c] = st.column_config.TextColumn(c, help=exit_help.get(c))

        st.dataframe(exit_df, use_container_width=True, hide_index=True,
                      column_config=col_cfg_exit)

        with st.expander("出場規則說明"):
            st.markdown("""
- **停損價** — 跌破即全出，由 MA20 與近 10 日低點取較高者
- **目標 1 (+1R)** — 觸及賣出 1/2 鎖利（剩餘半倉轉移動停利）
- **目標 2 (+2R)** — 觸及全部出清
- **移動停利 (MA10)** — 已有 5% 以上獲利時，跌破 MA10 全出鎖利
- **時間停損** — 進場後 10 個交易日仍未到 +1R 全出（換股提升資金效率）
- **技術轉弱** — K 死叉 D 且跌破 MA20 → 動能消失，提早出場
            """)

        h_buf = io.BytesIO()
        with pd.ExcelWriter(h_buf, engine="openpyxl") as writer:
            h_df.to_excel(writer, sheet_name="持股賣出建議", index=False)
        h_buf.seek(0)
        st.download_button(
            "下載持股報告", data=h_buf.getvalue(),
            file_name="持股賣出建議.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
