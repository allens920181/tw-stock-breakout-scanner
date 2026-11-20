"""持股分析流程：逐檔給出場建議（停損 / +1R / +2R / 時間停損 / 移動停利）"""
import logging

import pandas as pd

from twscanner.core import cache as cache_mod
from twscanner.data.chips import fetch_chips
from twscanner.data.prices import (
    resolve_markets_and_data,
)
from twscanner.data.revenue import fetch_revenue
from twscanner.market.tw_regime import classify_market
from twscanner.portfolio.holdings import analyze_holding, load_holdings

log = logging.getLogger(__name__)


def run_holdings_scan(holdings_path=None, cfg=None, progress_cb=None, holdings=None):
    """
    掃描持股賣出建議。
    holdings_path: 從 Excel 讀；或
    holdings: 直接傳 list[{code, company_name, entry_price, entry_date, shares}]
    """
    def emit(stage, pct, msg):
        log.info("[%s] %s", stage, msg)
        if progress_cb:
            try:
                progress_cb(stage, pct, msg)
            except Exception:
                pass

    cache_mod.ensure_dir(cfg["data"]["cache_dir"])
    if holdings is None:
        emit("讀取持股", 0.05, f"讀取 {holdings_path}")
        holdings = load_holdings(holdings_path, cfg["etf_fix_map"])
    emit("讀取持股", 0.10, f"讀入 {len(holdings)} 檔持股")

    items = [{"code": h["code"], "company_name": h["company_name"]} for h in holdings]
    emit("下載資料", 0.20, "批次下載歷史")
    resolved, not_found = resolve_markets_and_data(
        items, cfg["data"]["period"], cfg["data"]["cache_dir"],
        chunk_size=cfg["data"].get("chunk_size", 50),
        chunk_sleep=cfg["data"].get("chunk_sleep", 1.0),
    )
    emit("下載資料", 0.70, f"定位 {len(resolved)} 檔")

    code_to_resolved = {r["symbol"].split(".")[0]: r for r in resolved}

    # 持股期間主動示警所需的籌碼/營收/大盤（best-effort，失敗不影響出場規則）
    chips_map, revenue_map, market_state = {}, {}, None
    try:
        if cfg.get("chips", {}).get("enabled", True):
            chips_map = fetch_chips(
                cfg["data"]["cache_dir"],
                days=cfg.get("chips", {}).get("streak_days", 5),
                verify=cfg.get("chips", {}).get("verify_ssl", True))
    except Exception as e:
        log.warning("持股籌碼抓取失敗：%s", e)
    try:
        if cfg.get("revenue", {}).get("enabled", True):
            revenue_map = fetch_revenue(
                cfg["data"]["cache_dir"],
                verify=cfg.get("revenue", {}).get("verify_ssl", True))
    except Exception as e:
        log.warning("持股營收抓取失敗：%s", e)
    try:
        if cfg.get("market_filter", {}).get("enabled", True):
            market_state = classify_market(cfg["data"]["period"], cfg["data"]["cache_dir"])
            bm_cfg = cfg.get("bigmoney", {})
            if bm_cfg.get("enabled", True):
                from datetime import timedelta

                from twscanner.core.tz import today_tw
                from twscanner.market.bigmoney import classify_bigmoney
                today = today_tw()
                mdates = [(today - timedelta(days=k)).strftime("%Y%m%d") for k in range(0, 9)]
                market_state["big_state"] = classify_bigmoney(
                    cache_dir=cfg["data"]["cache_dir"],
                    verify=bm_cfg.get("verify_ssl", True),
                    margin_dates=mdates, weights=bm_cfg.get("weights"))
    except Exception as e:
        log.warning("持股大盤判斷失敗：%s", e)

    rows = []
    for h in holdings:
        # 兼容舊 key "lots" 與新 key "shares"（舊 lots × 1000 = shares）
        shares_val = h.get("shares")
        if shares_val is None and h.get("lots") is not None:
            try:
                shares_val = int(h["lots"]) * 1000
            except Exception:
                shares_val = h.get("lots")

        r = code_to_resolved.get(h["code"])
        if r is None:
            rows.append({
                "股票": h["code"], "公司名稱": h["company_name"], "市場": None,
                "進場日": str(h["entry_date"]) if h["entry_date"] else None,
                "持有天數": None, "進場價": h["entry_price"],
                "目前價": None, "報酬%": None, "R倍數": None,
                "持有股數": shares_val,
                "操作建議": "找不到資料", "賣出量": "—",
                "說明": "市場未定位", "狀態": "找不到",
            })
            continue
        hcfg = cfg.get("holdings", {})
        row = analyze_holding(
            r["symbol"], r["company_name"] or h["company_name"], r["market"],
            r["df"], h["entry_price"], h["entry_date"], shares_val,
            time_stop_days=hcfg.get("time_stop_days", 10),
            atr_trail_mult=hcfg.get("atr_trail_mult", 3.0),
            let_winners_run=hcfg.get("let_winners_run", True),
            strong_adx=hcfg.get("strong_adx", 25.0),
            strong_streak=hcfg.get("strong_streak", 3),
            strong_vol_mult=hcfg.get("strong_vol_mult", 1.5),
            chips=chips_map.get(h["code"]),
            revenue=revenue_map.get(h["code"]),
            market_state=market_state,
        )
        rows.append(row)

    df_h = pd.DataFrame(rows)
    emit("完成", 1.0, f"持股分析完成 {len(df_h)} 檔")
    return {"df": df_h}


