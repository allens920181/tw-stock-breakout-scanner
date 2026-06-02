"""可重用掃描流程：CLI 與 GUI 共用"""
import logging
import time

import pandas as pd

from . import cache as cache_mod
from .fetcher import (
    fetch_all_current_prices,
    fetch_all_shares,
    load_stock_list,
    resolve_markets_and_data,
)
from .ambush import analyze_ambush
from .backtest import (
    backtest_symbol, summarize_by_regime, summarize_trades, summarize_trades_is_oos,
)
from .chips import fetch_chips
from .earnings import fetch_all_earnings
from .factor_eval import evaluate_factors, suggest_weights_from_lift
from .margin import fetch_margin
from .sectors import annotate_group_strength, apply_sector_heat, fetch_sectors
from .holdings import analyze_holding, load_holdings
from .macro import classify_us_market, merge_position_factor
from .market import classify_market
from .report import build_dataframes
from .scoring import analyze_stock
from .sensitivity import detect_plateau, plateau_scan, sensitivity_scan

log = logging.getLogger(__name__)


def run_scan(input_path=None, cfg=None, progress_cb=None, items=None):
    """
    progress_cb(stage: str, pct: float, message: str) — 可選回呼
    items: 可選；直接傳入 [{code, company_name}] 跳過 Excel 讀取

    Returns: dict 含 df / summary / failed_df / elapsed_sec
    """
    def emit(stage, pct, msg):
        log.info("[%s] %s", stage, msg)
        if progress_cb:
            try:
                progress_cb(stage, pct, msg)
            except Exception:
                pass

    t0 = time.time()
    cache_mod.ensure_dir(cfg["data"]["cache_dir"])

    if items is None:
        emit("讀取清單", 0.05, f"讀取 {input_path}")
        items = load_stock_list(input_path, cfg["etf_fix_map"])
    emit("讀取清單", 0.10, f"讀入 {len(items)} 檔")

    emit("下載資料", 0.15, "批次下載 OHLC ...")
    resolved, not_found = resolve_markets_and_data(
        items, cfg["data"]["period"], cfg["data"]["cache_dir"],
        chunk_size=cfg["data"].get("chunk_size", 50),
        chunk_sleep=cfg["data"].get("chunk_sleep", 1.0),
    )
    emit("下載資料", 0.50, f"定位 {len(resolved)} 檔，{len(not_found)} 檔失敗")

    emit("抓股數", 0.55, f"平行抓 {len(resolved)} 檔股數")
    symbols = [r["symbol"] for r in resolved]
    shares_map = fetch_all_shares(
        symbols, cfg["data"]["cache_dir"], cfg["data"]["max_workers"],
    )
    emit("抓股數", 0.76, "完成")

    emit("抓現價", 0.77, f"平行抓 {len(resolved)} 檔現價")
    price_map = fetch_all_current_prices(
        symbols, cfg["data"]["max_workers"],
    )
    emit("抓現價", 0.78, "完成")

    chips_map = {}
    chip_cfg = cfg.get("chips", {})
    if chip_cfg.get("enabled", True):
        emit("抓籌碼", 0.785, "抓三大法人 / 外資買賣超")
        try:
            chips_map = fetch_chips(
                cfg["data"]["cache_dir"],
                days=chip_cfg.get("streak_days", 5),
                verify=chip_cfg.get("verify_ssl", True),
            )
            emit("抓籌碼", 0.79, f"籌碼 {len(chips_map)} 檔")
        except Exception as e:
            log.warning("籌碼抓取失敗，略過：%s", e)

    margin_map = {}
    mgn_cfg = cfg.get("margin", {})
    if mgn_cfg.get("enabled", True):
        emit("抓融資券", 0.792, "抓融資餘額 / 券資比")
        try:
            margin_map = fetch_margin(
                cfg["data"]["cache_dir"],
                verify=mgn_cfg.get("verify_ssl", True),
            )
            emit("抓融資券", 0.795, f"融資券 {len(margin_map)} 檔")
        except Exception as e:
            log.warning("融資券抓取失敗，略過：%s", e)

    earnings_map = {}
    earn_cfg = cfg.get("earnings", {})
    if earn_cfg.get("enabled", True):
        emit("抓財報日", 0.797, f"抓 {len(resolved)} 檔下一財報日")
        try:
            earnings_map = fetch_all_earnings(
                symbols, cfg["data"]["cache_dir"], cfg["data"]["max_workers"],
            )
            emit("抓財報日", 0.80, "完成")
        except Exception as e:
            log.warning("財報日抓取失敗，略過：%s", e)

    market_state = None
    us_state = None
    if cfg.get("market_filter", {}).get("enabled", True):
        emit("大盤判斷", 0.79, "抓 ^TWII 判斷台股大盤")
        market_state = classify_market(
            cfg["data"]["period"], cfg["data"]["cache_dir"],
        )
        emit("大盤判斷", 0.80, f"台股 {market_state['label']} — {market_state['detail']}")

        emit("大盤判斷", 0.80, "抓 ^VIX / ^GSPC 判斷美股風險偏好")
        us_state = classify_us_market(
            period="1y", cache_dir=cfg["data"]["cache_dir"],
        )
        emit("大盤判斷", 0.81,
             f"美股 {us_state['label']} — {us_state['detail']}")

        # 合併雙因子：取較保守者
        combined_factor = merge_position_factor(market_state, us_state)
        if market_state:
            market_state["position_factor"] = combined_factor
            market_state["us_state"] = us_state

    mode = cfg.get("strategy", {}).get("mode", "breakout")
    analyze_fn = analyze_ambush if mode == "ambush" else analyze_stock
    emit("分析", 0.82, f"逐檔分析 {len(resolved)} 檔（模式：{mode}）")
    results = []
    failed_list = []
    total = max(len(resolved), 1)
    for i, r in enumerate(resolved):
        try:
            res = analyze_fn(
                r["symbol"], r["company_name"], r["market"],
                r["df"], shares_map.get(r["symbol"]), cfg,
                market_state=market_state,
                current_price=price_map.get(r["symbol"]),
                chips=chips_map.get(r["symbol"].split(".")[0]),
                margin=margin_map.get(r["symbol"].split(".")[0]),
                earnings_date=earnings_map.get(r["symbol"]),
            )
            results.append(res)
        except Exception as e:
            log.exception("分析失敗：%s", r["symbol"])
            failed_list.append({
                "股票": r["symbol"], "公司名稱": r["company_name"],
                "市場": r["market"], "錯誤訊息": str(e),
            })
        if (i + 1) % 20 == 0:
            emit("分析", 0.82 + 0.15 * (i + 1) / total,
                 f"分析 {i + 1}/{total}")

    for code, name in not_found:
        failed_list.append({
            "股票": code, "公司名稱": name, "市場": None,
            "錯誤訊息": "非上市或查無資料",
        })

    # 族群同步：跨檔後處理（同產業強勢檔數）
    if cfg.get("sectors", {}).get("enabled", True):
        emit("族群同步", 0.985, "計算同產業強勢檔數")
        try:
            sectors_map = fetch_sectors(
                cfg["data"]["cache_dir"],
                verify=cfg.get("sectors", {}).get("verify_ssl", True),
            )
            annotate_group_strength(results, sectors_map)
            if cfg.get("sectors", {}).get("heat_enabled", True):
                apply_sector_heat(
                    results,
                    heat_max=cfg.get("sectors", {}).get("heat_max", 3),
                )
        except Exception as e:
            log.warning("族群同步計算失敗，略過：%s", e)

    elapsed = time.time() - t0
    df, summary, failed_df = build_dataframes(
        results, failed_list, len(items), elapsed,
    )
    emit("完成", 1.0, f"總耗時 {elapsed:.1f} 秒")

    # 為彈窗 K 線圖保留 OHLC（symbol → DataFrame）
    ohlc_map = {r["symbol"]: r["df"] for r in resolved}

    return {
        "df": df,
        "summary": summary,
        "failed_df": failed_df,
        "elapsed_sec": elapsed,
        "market_state": market_state,
        "ohlc_map": ohlc_map,
    }


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

    sym_to_df = {r["symbol"]: r for r in resolved}
    code_to_resolved = {r["symbol"].split(".")[0]: r for r in resolved}

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
        row = analyze_holding(
            r["symbol"], r["company_name"] or h["company_name"], r["market"],
            r["df"], h["entry_price"], h["entry_date"], shares_val,
        )
        rows.append(row)

    df_h = pd.DataFrame(rows)
    emit("完成", 1.0, f"持股分析完成 {len(df_h)} 檔")
    return {"df": df_h}


def run_backtest(input_path, cfg, lookback_days=120, hold_days=10,
                 min_score=None, items=None, progress_cb=None,
                 oos_ratio=None, oos_mode=None):
    """對指定清單做 walk-forward 回測"""
    def emit(stage, pct, msg):
        log.info("[%s] %s", stage, msg)
        if progress_cb:
            try:
                progress_cb(stage, pct, msg)
            except Exception:
                pass

    cache_mod.ensure_dir(cfg["data"]["cache_dir"])

    if items is None:
        items = load_stock_list(input_path, cfg["etf_fix_map"])
    emit("讀取清單", 0.05, f"讀入 {len(items)} 檔")

    emit("下載資料", 0.10, "批次下載 ...")
    resolved, not_found = resolve_markets_and_data(
        items, cfg["data"]["period"], cfg["data"]["cache_dir"],
        chunk_size=cfg["data"].get("chunk_size", 50),
        chunk_sleep=cfg["data"].get("chunk_sleep", 1.0),
    )
    emit("下載資料", 0.50, f"定位 {len(resolved)} 檔")

    weights = cfg["scoring"]["weights"]
    costs = cfg.get("costs")
    if min_score is None:
        min_score = cfg["scoring"]["thresholds"]["strong"]

    regime_map = None
    if cfg.get("backtest", {}).get("regime_split", {}).get("enabled", True):
        from .market import build_regime_map
        try:
            regime_map = build_regime_map(cfg["data"]["period"], cfg["data"]["cache_dir"])
        except Exception as e:
            log.warning("regime_map 建立失敗：%s", e)

    emit("回測", 0.55, f"逐檔回測 (min_score={min_score}, hold={hold_days}, lookback={lookback_days})")

    all_trades = []
    by_symbol = []
    total = max(len(resolved), 1)
    for i, r in enumerate(resolved):
        try:
            trades = backtest_symbol(
                r["df"], weights, min_score,
                hold_days=hold_days, lookback=lookback_days, costs=costs,
                regime_map=regime_map,
            )
            for t in trades:
                t["股票"] = r["symbol"]
                t["公司名稱"] = r["company_name"]
            all_trades.extend(trades)

            if trades:
                stats = summarize_trades(trades)
                stats["股票"] = r["symbol"]
                stats["公司名稱"] = r["company_name"]
                by_symbol.append(stats)
        except Exception as e:
            log.warning("回測失敗 %s：%s", r["symbol"], e)

        if (i + 1) % 50 == 0:
            emit("回測", 0.55 + 0.4 * (i + 1) / total,
                 f"回測 {i+1}/{total}，累計 {len(all_trades)} 筆交易")

    trades_df = pd.DataFrame(all_trades)
    cols_order = ["股票", "公司名稱", "entry_date", "entry_price",
                  "exit_date", "exit_price", "exit_reason",
                  "return_pct", "r_multiple", "held_days", "score"]
    if len(trades_df):
        trades_df = trades_df[[c for c in cols_order if c in trades_df.columns]]

    summary = summarize_trades(all_trades, cfg)

    # 樣本外驗證（IS/OOS）
    bt_cfg = cfg.get("backtest", {})
    if oos_ratio is None:
        oos_ratio = bt_cfg.get("oos_ratio", 0.3) if bt_cfg.get("oos_enabled", True) else 0
    if oos_mode is None:
        oos_mode = bt_cfg.get("oos_mode", "ratio")
    oos_split = summarize_trades_is_oos(
        all_trades, cfg, oos_ratio=oos_ratio, mode=oos_mode,
        n_folds=bt_cfg.get("oos_n_folds", 3),
    )

    by_symbol_df = pd.DataFrame(by_symbol).sort_values(
        by="期望值R", ascending=False,
    ) if by_symbol else pd.DataFrame()

    emit("完成", 1.0, f"回測完成：{summary['總交易數']} 筆交易，勝率 {summary['勝率%']}%")
    return {
        "oos_split": oos_split,
        "by_regime": summarize_by_regime(all_trades, cfg),
        "trades": trades_df,
        "summary": summary,
        "by_symbol": by_symbol_df,
        "resolved": resolved,
    }


def run_factor_eval(input_path, cfg, lookback_days=250, hold_days=10,
                    items=None, resolved=None, progress_cb=None):
    """因子增量貢獻驗證。可直接帶 resolved（從回測結果重用）以省下載。"""
    def emit(stage, pct, msg):
        log.info("[%s] %s", stage, msg)
        if progress_cb:
            try:
                progress_cb(stage, pct, msg)
            except Exception:
                pass

    cache_mod.ensure_dir(cfg["data"]["cache_dir"])
    if resolved is None:
        if items is None:
            items = load_stock_list(input_path, cfg["etf_fix_map"])
        emit("下載資料", 0.1, f"讀入 {len(items)} 檔")
        resolved, _ = resolve_markets_and_data(
            items, cfg["data"]["period"], cfg["data"]["cache_dir"],
            chunk_size=cfg["data"].get("chunk_size", 50),
            chunk_sleep=cfg["data"].get("chunk_sleep", 1.0),
        )
    emit("因子驗證", 0.5, f"逐棒評估 {len(resolved)} 檔")
    result = evaluate_factors(resolved, cfg, lookback=lookback_days, hold_days=hold_days)
    emit("完成", 1.0, "因子驗證完成")
    return result


def run_weight_suggest(cfg, fe_result=None, resolved=None,
                       lookback_days=250, hold_days=10):
    """依因子驗證的 lift(R) 建議權重。優先用既有 fe_result。"""
    if fe_result is None:
        if resolved is None:
            raise ValueError("需提供 fe_result 或 resolved")
        fe_result = evaluate_factors(resolved, cfg, lookback=lookback_days, hold_days=hold_days)
    lw = cfg.get("scoring", {}).get("lift_weights", {})
    return suggest_weights_from_lift(
        fe_result, cfg,
        total=lw.get("total", 8),
        eps=lw.get("eps", 0.02),
        preserve_unverifiable=lw.get("preserve_unverifiable", ["turnover_strong"]),
    )


def run_plateau(resolved, cfg, param_name, grid, lookback_days, hold_days,
                progress_cb=None):
    """參數高原圖：一維掃描 + 高原/尖峰偵測。"""
    table = plateau_scan(resolved, cfg, param_name, grid, lookback_days, hold_days,
                         progress_cb=progress_cb)
    pcfg = cfg.get("sensitivity", {}).get("plateau", {})
    plateau = detect_plateau(
        table["param_value"].tolist(), table["期望值R"].tolist(),
        plateau_ratio=pcfg.get("plateau_ratio", 0.7),
        min_width=pcfg.get("min_width", 3),
        neighbor_w=pcfg.get("neighbor_w", 1),
        spike_drop=pcfg.get("spike_drop", 0.5),
    )
    return {"table": table, "plateau": plateau, "param_name": param_name}


def run_sensitivity(resolved, cfg, score_range, lookback_days, hold_days,
                    progress_cb=None):
    """跑多個 min_score 比較 edge。要先有 resolved（建議從 run_backtest 結果拿）"""
    def step_cb(i, total, sc):
        log.info("敏感度 %d/%d (score=%d)", i, total, sc)
        if progress_cb:
            try:
                progress_cb(i / total, sc)
            except Exception:
                pass
    return sensitivity_scan(
        resolved, cfg, score_range, lookback_days, hold_days, progress_cb=step_cb,
    )
