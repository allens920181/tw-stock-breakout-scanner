"""研究流程：回測、因子評估、權重建議、訊號日誌評估、壓力測試、自適應建議、參數高原/敏感度"""
import logging

import pandas as pd

from twscanner.core import cache as cache_mod
from twscanner.data.prices import (
    load_stock_list,
    resolve_markets_and_data,
)
from twscanner.research.backtest import (
    backtest_symbol,
    summarize_by_regime,
    summarize_trades,
    summarize_trades_is_oos,
)
from twscanner.research.factor_eval import evaluate_factors, suggest_weights_from_lift
from twscanner.research.sensitivity import detect_plateau, plateau_scan, sensitivity_scan

log = logging.getLogger(__name__)


def live_rules_from_cfg(cfg):
    """回測照實盤會下單的條件：空頭不進場、品質過濾、停損距離下限、跳空以開盤價停損。"""
    if not cfg.get("backtest", {}).get("live_rules", True):
        return None
    f = cfg.get("filters", {})
    return {
        "blocked_regimes": {"bear"} if cfg.get("market_filter", {}).get("enabled", True) else set(),
        "min_price": f.get("min_price", 0),
        "min_avg_volume": f.get("min_avg_volume", 0),
        "require_ma60": f.get("require_above_ma60", False),
        "min_risk_pct": f.get("min_risk_pct", 0),
        "gap_fill": True,
    }


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

    live_rules = live_rules_from_cfg(cfg)
    regime_map = None
    if cfg.get("backtest", {}).get("regime_split", {}).get("enabled", True) or live_rules:
        from twscanner.market.tw_regime import build_regime_map
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
                regime_map=regime_map, live_rules=live_rules,
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


def run_evaluate_journal(cfg, records=None, progress_cb=None):
    """前向訊號日誌（live OOS）：抓日誌標的後續 OHLC → 模擬出場 → 彙整實戰績效。"""
    from twscanner.portfolio.journal import (
        evaluate_journal,
        load_journal,
        summarize_journal,
    )

    def emit(stage, pct, msg):
        log.info("[%s] %s", stage, msg)
        if progress_cb:
            try:
                progress_cb(stage, pct, msg)
            except Exception:
                pass

    cache_mod.ensure_dir(cfg["data"]["cache_dir"])
    if records is None:
        records = load_journal()
    if not records:
        return {"evaluated": [], "summary": summarize_journal([]), "records": []}

    codes = sorted({str(r.get("股票", "")).split(".")[0] for r in records if r.get("股票")})
    items = [{"code": c, "company_name": ""} for c in codes if c]
    emit("評估日誌", 0.2, f"抓 {len(items)} 檔後續價格")
    resolved, _ = resolve_markets_and_data(
        items, cfg["data"]["period"], cfg["data"]["cache_dir"],
        chunk_size=cfg["data"].get("chunk_size", 50),
        chunk_sleep=cfg["data"].get("chunk_sleep", 1.0),
    )
    df_map = {}
    for r in resolved:
        df = r["df"]
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df_map[r["symbol"]] = df
    emit("評估日誌", 0.7, "模擬出場、計算實際 R")
    evaluated = evaluate_journal(records, df_map)
    summary = summarize_journal(evaluated)
    emit("完成", 1.0, f"已結案 {summary['已結案']} 筆，進行中 {summary['進行中']} 筆")
    return {"evaluated": evaluated, "summary": summary, "records": records}


def run_stress_test(resolved, cfg, mult=3.0, lookback_days=120, hold_days=10,
                    min_score=None):
    """
    壓力情境回測：把滑價放大 mult 倍重跑，回傳 base vs stress 摘要對比。
    模擬跳空/漲停打開等惡劣成交，檢查 edge 在最壞情況下是否仍存活。
    """
    import copy as _copy

    weights = cfg["scoring"]["weights"]
    if min_score is None:
        min_score = cfg["scoring"]["thresholds"].get("enter", 7)

    def _run(costs):
        trades = []
        for r in resolved:
            try:
                trades.extend(backtest_symbol(
                    r["df"], weights, min_score,
                    hold_days=hold_days, lookback=lookback_days, costs=costs,
                ))
            except Exception:
                pass
        return summarize_trades(trades, cfg)

    base_costs = cfg.get("costs", {})
    base = _run(base_costs)
    stress_costs = _copy.deepcopy(base_costs)
    stress_costs["enabled"] = True
    stress_costs["slippage_pct"] = base_costs.get("slippage_pct", 0.0015) * mult
    stress = _run(stress_costs)
    return {
        "mult": mult,
        "base_slippage_pct": base_costs.get("slippage_pct", 0.0015),
        "stress_slippage_pct": stress_costs["slippage_pct"],
        "base": base, "stress": stress,
    }


def run_adaptive_recommend(resolved, cfg, lookback_days=120, hold_days=10,
                           targets=("thresholds", "weights", "regime"),
                           fe_result=None, progress_cb=None):
    """建議模式：依回測自動產生參數/權重/regime 門檻建議（只建議，不自動套用）。"""
    from twscanner.research.adaptive import recommend_from_backtest
    return recommend_from_backtest(
        resolved, cfg, lookback=lookback_days, hold_days=hold_days,
        targets=targets, fe_result=fe_result, progress_cb=progress_cb,
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
