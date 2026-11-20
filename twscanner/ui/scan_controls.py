"""
掃描控制列（找標的頁頂端）：範圍 · 策略 · 風格 · 開始掃描。

參考成熟產品的篩選列：每個選項是一顆「標籤 · 目前值」的按鈕，點開才看到選項，
桌機一列排完、手機自動換行，不需要側欄。其他頁（今日決策、策略驗證）用 current_scan_state()
讀同一組設定，不重畫控制項。
"""
import hashlib
from dataclasses import dataclass, field

import streamlit as st

from twscanner.ui.components.common import make_stock_list_template
from twscanner.ui.settings import apply_preset
from twscanner.ui.state import get_base_config, seed

MODE_LABELS = {"breakout": "強勢突破", "early": "早期突破", "ambush": "潛伏起漲前"}
MODE_HELP = {
    "breakout": "追強勢：突破創高、量增、法人買。買已經在漲的。",
    "early": "只抓剛突破、還沒漲太遠的，避免追高。",
    "ambush": "起漲前埋伏：窄幅整理、量縮、站穩均線、接近但還沒突破。",
}
SOURCE_LABELS = {"universe": "全台股", "upload": "上傳清單"}
UNIVERSE_LABELS = {"twse": "上市普通股 + ETF", "twse-common": "僅普通股", "twse-etf": "僅 ETF"}


@dataclass
class ScanState:
    """掃描要用的資料來源與本次互動結果。"""
    mode: str                 # "掃描全台股" / "上傳清單"
    uploaded: object          # 有 getvalue() 的物件（或 None）
    universe_kind: str        # twse / twse-common / twse-etf
    run_btn: bool = False     # 本次是否按下「開始掃描」
    mode_labels: dict = field(default_factory=lambda: dict(MODE_LABELS))


class _Upload:
    """上傳檔存成 bytes，換頁後仍可用（file_uploader 的值離開頁面就會被清掉）。"""

    def __init__(self, name, data):
        self.name, self._data = name, data

    def getvalue(self):
        return self._data


def scope_key(sb):
    """範圍的識別：換了範圍（或換了上傳檔）就不同。"""
    if sb.mode == "掃描全台股":
        return f"universe:{sb.universe_kind}"
    if sb.uploaded:
        data = sb.uploaded.getvalue()
        return f"upload:{getattr(sb.uploaded, 'name', '')}:{hashlib.md5(data).hexdigest()}"
    return "upload:none"


def scope_label(sb):
    if sb.mode == "掃描全台股":
        return f"全台股（{UNIVERSE_LABELS.get(sb.universe_kind, sb.universe_kind)}）"
    return f"上傳清單 {getattr(sb.uploaded, 'name', '')}" if sb.uploaded else "上傳清單（未選檔）"


def current_scan_state(run_btn=False):
    source = st.session_state.get("scan_source", "universe")
    up = st.session_state.get("uploaded_list")
    return ScanState(
        mode="掃描全台股" if source == "universe" else "上傳清單",
        uploaded=_Upload(up["name"], up["data"]) if (source == "upload" and up) else None,
        universe_kind=st.session_state.get("universe_kind", "twse"),
        run_btn=run_btn)


def _source_label():
    if st.session_state.get("scan_source", "universe") == "upload":
        up = st.session_state.get("uploaded_list")
        return f"範圍 · {up['name']}" if up else "範圍 · 上傳清單（未選檔）"
    return f"範圍 · {UNIVERSE_LABELS.get(st.session_state.get('universe_kind', 'twse'), '全台股')}"


def _store_upload():
    """上傳後立刻存成 bytes（callback 在重畫前執行，範圍按鈕的標籤才會是新檔名）。"""
    f = st.session_state.get("scan_upload")
    if f is not None:
        st.session_state["uploaded_list"] = {"name": f.name, "data": f.getvalue()}


def render_scan_controls():
    """畫出控制列，回傳 ScanState（含本次是否按下開始掃描）。"""
    base_cfg = get_base_config()
    seed("scan_source", "universe")
    seed("universe_kind", "twse")
    seed("strategy_mode", "breakout")
    presets = {k: base_cfg["presets"][k]["label"] for k in ("conservative", "balanced", "aggressive")}

    bar = st.container(key="scanbar")             # CSS 用 .st-key-scanbar：手機排成 2×2，不疊成四列
    c1, c2, c3, c4 = bar.columns([1.5, 1.1, 1.0, 0.9], vertical_alignment="bottom")
    with c1.popover(_source_label(), use_container_width=True):
        st.segmented_control("資料來源", list(SOURCE_LABELS), format_func=SOURCE_LABELS.get, required=True,
                             key="scan_source", label_visibility="collapsed")
        if st.session_state.get("scan_source") == "upload":
            st.file_uploader("上傳 xlsx（欄位：股票代號、公司名稱）", type=["xlsx"], key="scan_upload",
                             on_change=_store_upload)
            st.download_button("下載清單範本", data=make_stock_list_template(), file_name="股票清單_範本.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.radio("範圍", list(UNIVERSE_LABELS), format_func=UNIVERSE_LABELS.get, key="universe_kind")
            st.caption("全台股第一次約 5–15 分鐘；同一天再掃不到 1 分鐘。")
    mode = st.session_state.get("strategy_mode") or "breakout"
    with c2.popover(f"策略 · {MODE_LABELS.get(mode, mode)}", use_container_width=True):
        st.radio("策略", list(MODE_LABELS), format_func=MODE_LABELS.get, key="strategy_mode",
                 captions=[MODE_HELP[k] for k in MODE_LABELS], label_visibility="collapsed")
    cur = st.session_state.get("preset", "balanced")
    with c3.popover(f"風格 · {presets.get(cur, cur)}", use_container_width=True):
        picked = st.radio("風格", list(presets), format_func=presets.get, index=list(presets).index(cur),
                          key="_preset_pick", label_visibility="collapsed",
                          captions=["門檻嚴、單筆風險小", "預設", "門檻寬、單筆風險大"])
        if picked != cur:
            apply_preset(picked)
            st.rerun()
    run = c4.button("開始掃描", type="primary", use_container_width=True, key="scan_run")
    return current_scan_state(run_btn=run)
