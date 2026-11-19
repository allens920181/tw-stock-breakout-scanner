"""實戰績效（前向訊號日誌）與掃描歷史（策略驗證頁的分頁）。"""

import pandas as pd
import streamlit as st

from twscanner.services import run_evaluate_journal
from twscanner.storage import cloud as store
from twscanner.storage.history import list_scans, load_scan_df
from twscanner.ui.format import clean_stock_col
from twscanner.ui.settings import build_cfg
from twscanner.ui.state import cloud_owner


def render():
    """實戰績效與掃描歷史"""
    # ===== 訊號實戰績效（live OOS）=====
    st.markdown("### 實戰績效：系統發出的訊號後來怎麼樣")
    st.caption(
        "回測是歷史模擬；**這裡是真帳**——每次掃描的「進場」清單自動存檔，"
        "用後續真實價格量**實際 R**，檢查系統實戰準不準。樣本要時間累積，越跑越準。"
    )
    from twscanner.portfolio.journal import load_journal, save_journal
    _jrecords = load_journal()
    jc1, jc2, jc3 = st.columns([1.4, 1, 1])
    jc1.caption(f"日誌累計 {len(_jrecords)} 筆進場訊號")
    eval_btn = jc2.button("評估實戰績效", key="eval_journal",
                          use_container_width=True, disabled=not _jrecords)
    if jc3.button("清空日誌", key="clear_journal", use_container_width=True,
                  disabled=not _jrecords):
        save_journal([])
        if cloud_owner():
            store.save_journal(cloud_owner(), [])
        st.session_state.pop("journal_eval", None)
        st.toast("已清空訊號日誌", icon="🗑")
        st.rerun()
    if eval_btn:
        cfg = build_cfg()
        with st.spinner("抓後續價格、計算實際 R …"):
            try:
                st.session_state["journal_eval"] = run_evaluate_journal(cfg)
            except Exception as e:
                st.error(f"評估失敗：{e}")
    if st.session_state.get("journal_eval"):
        je = st.session_state["journal_eval"]
        s = je["summary"]
        m = st.columns(4)
        m[0].metric("已結案", f"{s['已結案']} / {s['總訊號數']}")
        m[1].metric("勝率%", s["勝率%"] if s["勝率%"] is not None else "—")
        m[2].metric("已結案期望值R", s["已結案期望值R"] if s["已結案期望值R"] is not None else "—")
        m[3].metric("進行中", s["進行中"])
        _exp = s["已結案期望值R"]
        if s["已結案"] and s["已結案"] < 20:
            st.warning(f"已結案僅 {s['已結案']} 筆 — 樣本太少，數字僅供參考，繼續累積。")
        elif _exp is not None and _exp > 0:
            st.success(f"實戰已結案期望值 +{_exp}R（{s['已結案']} 筆）— 系統在真實市場有正的期望值。")
        elif _exp is not None:
            st.error(f"實戰期望值 {_exp}R（{s['已結案']} 筆）— 與回測落差大，檢視參數是否過擬合。")
        if je["evaluated"]:
            jdf = pd.DataFrame(je["evaluated"])
            view_cols = [c for c in [
                "掃描日", "股票", "公司名稱", "模式", "綜合評級", "狀態",
                "實際R", "最佳R", "最差R", "持有天數", "出場日",
                "進場參考價", "停損價", "相對強度RS%"] if c in jdf.columns]
            st.dataframe(clean_stock_col(jdf[view_cols].sort_values("掃描日", ascending=False)),
                         use_container_width=True, hide_index=True)
    st.divider()

    st.markdown("### 掃描歷史")
    st.caption("自動保存最近 30 次掃描，可隨時回看當日結果。")
    scans = list_scans()
    if not scans:
        st.info("尚無歷史紀錄 — 跑一次掃描就會自動存檔")
    else:
        meta_df = pd.DataFrame([{
            "時間": s["timestamp"],
            "標籤": s["label"],
            "大盤": s.get("market", "—"),
            "掃描": s.get("n_total", 0),
            "進場": s.get("n_enter", 0),
            "觀察": s.get("n_watch", 0),
            "耗時(秒)": s.get("elapsed_sec", "—"),
            "_path": s["_path"],
        } for s in scans])
        display_meta = meta_df.drop(columns=["_path"])
        st.dataframe(display_meta, use_container_width=True, hide_index=True)

        sel = st.selectbox(
            "查看明細",
            options=meta_df["時間"].tolist(),
            index=0,
        )
        if sel:
            row = meta_df[meta_df["時間"] == sel].iloc[0]
            old_df = load_scan_df(row["_path"])
            if old_df is not None and len(old_df):
                st.markdown(f"**{sel}** — 進場 {row['進場']} · 觀察 {row['觀察']}")
                # 只顯示精簡欄位
                cols_pref = ["股票", "公司名稱", "操作建議", "評分顯示",
                              "進場參考價", "停損價", "風險%", "建議張數", "換手率%"]
                show_cols = [c for c in cols_pref if c in old_df.columns]
                st.dataframe(old_df[show_cols], use_container_width=True,
                              hide_index=True)
            else:
                st.warning("找不到該次掃描的資料檔")
