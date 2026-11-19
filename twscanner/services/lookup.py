"""單檔快速查詢（免跑全市場）：技術/籌碼/營收快照 + 有成本時給出場建議"""
import logging

from twscanner.analysis.health import health_report
from twscanner.core import cache as cache_mod
from twscanner.data.chips import fetch_chips
from twscanner.data.fundamentals import fetch_fundamentals
from twscanner.data.prices import (
    resolve_markets_and_data,
)
from twscanner.data.revenue import fetch_revenue
from twscanner.data.sectors import fetch_shares_official
from twscanner.market.tw_regime import classify_market
from twscanner.portfolio.holdings import analyze_holding
from twscanner.strategy.scoring import analyze_stock

log = logging.getLogger(__name__)


def run_single_lookup(code, cfg, company_name="", entry_price=None,
                      entry_date=None, with_bigmoney=False, progress_cb=None):
    """
    個股健檢：抓單檔的價量＋籌碼＋營收＋財報＋大盤，回傳
      {symbol, name, scoring(買入視角), holding(出場視角，有成本才算), health(財報白話健檢)}
    免跑全市場掃描；資料源各自快取，同日第二次查很快。
    """
    def emit(p, msg):
        if progress_cb:
            try:
                progress_cb(p, msg)
            except Exception:
                pass

    cache_mod.ensure_dir(cfg["data"]["cache_dir"])
    code = str(code).strip()
    fixed = cfg.get("etf_fix_map", {}).get(code, code)
    if fixed.isdigit() and len(fixed) < 4:
        fixed = fixed.zfill(4)

    emit(0.15, "下載價量")
    resolved, not_found = resolve_markets_and_data(
        [{"code": fixed, "company_name": company_name}],
        cfg["data"]["period"], cfg["data"]["cache_dir"],
        chunk_size=cfg["data"].get("chunk_size", 50),
        chunk_sleep=cfg["data"].get("chunk_sleep", 1.0),
    )
    if not resolved:
        return {"error": f"查無資料：{code}（非上市或代碼錯誤）"}
    r = resolved[0]
    sym = r["symbol"]
    df = r["df"]

    emit(0.4, "抓流通股數")
    shares = None
    try:
        shares = fetch_shares_official(
            cfg["data"]["cache_dir"],
            verify=cfg.get("sectors", {}).get("verify_ssl", True)).get(fixed)
    except Exception:
        pass

    emit(0.5, "抓籌碼 / 營收")
    chips = revenue = None
    try:
        if cfg.get("chips", {}).get("enabled", True):
            chips = fetch_chips(cfg["data"]["cache_dir"],
                                days=cfg.get("chips", {}).get("streak_days", 5),
                                verify=cfg.get("chips", {}).get("verify_ssl", True)).get(fixed)
    except Exception as e:
        log.warning("查詢籌碼失敗：%s", e)
    try:
        if cfg.get("revenue", {}).get("enabled", True):
            revenue = fetch_revenue(cfg["data"]["cache_dir"],
                                    verify=cfg.get("revenue", {}).get("verify_ssl", True)).get(fixed)
    except Exception as e:
        log.warning("查詢營收失敗：%s", e)

    emit(0.7, "判斷大盤")
    market_state = None
    try:
        if cfg.get("market_filter", {}).get("enabled", True):
            market_state = classify_market(cfg["data"]["period"], cfg["data"]["cache_dir"])
            if with_bigmoney and cfg.get("bigmoney", {}).get("enabled", True):
                from datetime import timedelta

                from twscanner.core.tz import today_tw
                from twscanner.market.bigmoney import classify_bigmoney
                today = today_tw()
                mdates = [(today - timedelta(days=k)).strftime("%Y%m%d") for k in range(0, 9)]
                market_state["big_state"] = classify_bigmoney(
                    cache_dir=cfg["data"]["cache_dir"],
                    verify=cfg.get("bigmoney", {}).get("verify_ssl", True),
                    margin_dates=mdates, weights=cfg.get("bigmoney", {}).get("weights"))
    except Exception as e:
        log.warning("查詢大盤失敗：%s", e)

    # yfinance 盤中/收盤前常附一列 Close 為 NaN 的當日資料 → 取最後一個有效收盤
    current_price = float(df["Close"].dropna().iloc[-1])
    name = r["company_name"] or company_name or code

    emit(0.85, "分析")
    scoring = analyze_stock(
        sym, name, r["market"], df.copy(), shares, cfg,
        market_state=market_state, current_price=current_price,
        chips=chips, revenue=revenue,
    )
    holding = None
    if entry_price:
        hcfg = cfg.get("holdings", {})
        holding = analyze_holding(
            sym, name, r["market"], df.copy(), float(entry_price), entry_date,
            time_stop_days=hcfg.get("time_stop_days", 10),
            atr_trail_mult=hcfg.get("atr_trail_mult", 3.0),
            let_winners_run=hcfg.get("let_winners_run", True),
            strong_adx=hcfg.get("strong_adx", 25.0),
            strong_streak=hcfg.get("strong_streak", 3),
            strong_vol_mult=hcfg.get("strong_vol_mult", 1.5),
            chips=chips, revenue=revenue, market_state=market_state)

    emit(0.95, "財報健檢")
    fund = None
    try:
        fund = fetch_fundamentals(cfg["data"]["cache_dir"],
                                  verify=cfg.get("revenue", {}).get("verify_ssl", True)).get(fixed)
    except Exception as e:
        log.warning("查詢財報失敗：%s", e)
    health = health_report(fund, revenue, price=current_price)

    emit(1.0, "完成")
    return {"symbol": sym, "name": name, "scoring": scoring,
            "holding": holding, "df": df, "market_state": market_state,
            "fundamentals": fund, "revenue": revenue, "health": health}


