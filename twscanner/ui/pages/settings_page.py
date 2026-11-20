"""
設定：資金與月目標、顯示偏好、雲端帳號、進階（選股過濾、評分權重）。

以前全部擠在側欄；成熟產品把「不常改的設定」放在獨立的設定頁，主畫面只留每天要用的東西。
每個 widget 只給 key（值由 state.seed 帶預設、state.persist_settings 跨頁保留）。
"""
import streamlit as st

from twscanner.storage import cloud as store
from twscanner.storage.preferences import save_prefs
from twscanner.ui import sync
from twscanner.ui.glossary import HELP
from twscanner.ui.state import cloud_passcode, get_base_config, seed


def _section(title, desc):
    st.markdown(f"<div class='set-head'><div class='t'>{title}</div><div class='d'>{desc}</div></div>",
                unsafe_allow_html=True)


def _money(base_cfg):
    _section("資金與月目標", "決定每筆買幾張、每月最多能賠多少。")
    ps = base_cfg.get("position_sizing", {})
    # 一列一組（而不是左右兩欄各自往下排）：手機疊成一欄時順序才合理
    c1, c2 = st.columns(2)
    c1.number_input("總資金（元）", min_value=100_000, step=100_000, help=HELP["total_capital"],
                    key=seed("total_capital", int(ps.get("total_capital", 1_000_000))))
    c2.number_input("月目標（元）", min_value=0, step=1_000, key=seed("month_target", 10_000),
                    help="每月希望賺多少。系統用它推算每月要做幾筆，不會因此放大單筆風險。")
    c1, c2 = st.columns(2)
    c1.slider("單筆風險 %", 0.5, 5.0, step=0.25, key=seed("risk_pct", 1.0), help=HELP["risk_per_trade"])
    c2.number_input("每月虧損上限（R）", min_value=1.0, max_value=6.0, step=0.5, key=seed("loss_limit_r", 2.0),
                    help="本月已實現虧損達到幾筆停損的量就停手。1R = 一筆交易的最大虧損。")
    c1, c2 = st.columns(2)
    c1.slider("單檔最大佔比 %", 5, 50, step=5, key=seed("max_pos_pct", 20), help=HELP["max_pos_pct"])
    c2.slider("ATR 停損倍數", 1.0, 4.0, step=0.5,
              key=seed("f_atr_mult", float(base_cfg["filters"].get("atr_mult", 1.5))),
              help="停損 = 進場價 − ATR14 × 此倍數。")
    c1, _ = st.columns(2)
    c1.slider("流動性上限（部位 ≤ 此 % × 20 日均量）", 0, 30, step=5,
              key=seed("_max_adv_pct_pct", int(ps.get("max_adv_pct", 0.10) * 100)),
              help="避免小型股算出「進得去出不來」的部位。0 = 關閉。")
    st.session_state["max_adv_pct"] = st.session_state["_max_adv_pct_pct"] / 100


def _display():
    _section("顯示", "全站的漲跌、損益、多空燈號都依此上色。")
    st.radio("漲跌顏色", ["tw", "us"], key=seed("color_mode", "tw"), horizontal=True,
             format_func=lambda k: {"tw": "紅漲綠跌（台股習慣）", "us": "綠漲紅跌（美股習慣）"}[k])


def _save():
    if sync.owner():
        st.caption("已登入雲端：設定改了就會自動同步，換裝置登入也一樣。")
        return
    st.caption("沒有登入雲端：風格與漲跌顏色可以存在這台伺服器；總資金、月目標等財務數字只在登入雲端後保存"
               "（公開部署時，伺服器上的檔案是所有訪客共用的）。")
    if st.button("儲存風格與顏色"):
        res = save_prefs({"preset": st.session_state.get("preset", "balanced"),
                          "color_mode": st.session_state.get("color_mode", "tw"), "onboarded": True}, None)
        st.toast("已儲存" if res["local"] else "儲存失敗")


def _login():
    pc = cloud_passcode()
    if pc and st.session_state.get("cloud_pw") == pc:
        st.session_state["cloud_owner"] = "me"
        st.session_state.pop("_cloud_loaded", None)
        st.session_state.pop("cloud_pw", None)
    else:
        st.session_state["_login_error"] = True


def _cloud():
    if not store.is_enabled():
        return
    _section("雲端帳號", "登入後，持股、交易紀錄、訊號日誌與所有設定都會自動同步，換裝置也看得到。")
    if not sync.owner():
        c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
        c1.text_input("密碼", type="password", key="cloud_pw")
        c2.button("登入", type="primary", use_container_width=True, on_click=_login)
        if st.session_state.pop("_login_error", False):
            st.error("密碼錯誤，或伺服器沒有設定 APP_PASSCODE")
        return
    text, state = sync.status()
    m = st.session_state.get("_sync", {})
    rows = "".join(
        f"<div class='rowline'><div class='main'><div class='t'>{label}</div></div>"
        f"<div class='v'>{_count(key)}</div></div>" for key, label in sync.LABELS.items())
    st.markdown(f"<div class='sync-state {state}'><i class='dot {state}'></i>{text}</div>{rows}",
                unsafe_allow_html=True)
    if m.get("error"):
        st.caption(f"錯誤：{m['error']}（多半是網路或 DATABASE_URL 設定；資料先留在這個分頁，連上後會自動補傳）")
    b1, b2, _ = st.columns([1, 1, 2])
    b1.button("立即檢查更新", use_container_width=True, on_click=sync.pull_changes, kwargs={"force": True})
    b2.button("登出", use_container_width=True, on_click=sync.logout,
              help="登出後，這個分頁裡的持股、交易紀錄與日誌會一起清掉（雲端的不受影響）。")


def _count(key):
    v = sync.snapshot(key)
    if key == "prefs":
        return f"{len(v)} 項" if v else "—"
    return f"{len(v)} 筆" if v else "0 筆"


def _advanced(base_cfg):
    _section("進階：選股條件", "預設值來自研究與回測；不確定就不要改。改完回「找標的」重新掃描才會生效。")
    with st.expander("選股過濾"):
        c1, c2 = st.columns(2)
        c1.number_input("最低股價", min_value=0.0, step=1.0, key=seed("min_price", 10.0), help=HELP["min_price"])
        c2.number_input("20 日均量下限（股）", min_value=0, step=100_000, key=seed("min_avg_volume", 500_000),
                        help=HELP["min_avg_volume"])
        c1.slider("最小停損距離 %", 0.0, 10.0, step=0.5, help=HELP["min_risk_pct"],
                  key=seed("min_risk_pct_slider", st.session_state.get("min_risk_pct", 0.02) * 100))
        c2.checkbox("必須站上 MA60", key=seed("require_ma60", True), help=HELP["require_ma60"])
        amb = base_cfg.get("strategy", {}).get("ambush", {})
        c1.checkbox("潛伏模式：排除弱於大盤的股票", key=seed("amb_rs_gate", bool(amb.get("require_positive_rs", True))))
        c2.slider("潛伏模式 RS 門檻（%）", -5.0, 10.0, step=0.5, key=seed("amb_min_rs", float(amb.get("min_rs", 0.0))),
                  help="個股 60 日報酬須 ≥ 大盤 + 此值。")
    with st.expander("評分權重與門檻"):
        w = base_cfg["scoring"]["weights"]
        items = [("突破 + 量增", "w_breakout", w["breakout_with_volume"], "weight_breakout"),
                 ("MA 多頭", "w_ma", w["ma_bullish"], "weight_ma_bullish"),
                 ("換手率強勢", "w_turnover", w["turnover_strong"], "weight_turnover_strong"),
                 ("KD", "w_kd", w["kd"], "weight_kd"), ("MACD", "w_macd", w["macd"], "weight_macd"),
                 ("相對強度 RS", "w_rs", w.get("rel_strength", 1), "weight_rel_strength"),
                 ("趨勢確認", "w_trend", w.get("trend_confirm", 1), "weight_trend_confirm")]
        cols = st.columns(2)
        for k, (label, key, default, h) in enumerate(items):
            cols[k % 2].slider(label, 0, 5, key=seed(key, int(default)), help=HELP[h])
        total = sum(st.session_state[key] for _, key, _, _ in items)
        c1, c2 = st.columns(2)
        c1.number_input(f"進場 ≥（總分上限 {total}）", 0, 20, key=seed("thr_enter", 6), help=HELP["thr_enter"])
        c2.number_input("觀察 ≥", 0, 20, key=seed("thr_watch", 5), help=HELP["thr_watch"])


def render():
    base_cfg = get_base_config()
    st.markdown("<div class='page-title'>設定</div>", unsafe_allow_html=True)
    _money(base_cfg)
    _display()
    _save()
    _cloud()
    _advanced(base_cfg)
