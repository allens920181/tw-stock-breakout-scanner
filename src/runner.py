"""可重用掃描流程：CLI 與 GUI 共用"""
import logging
import time

import pandas as pd

from . import cache as cache_mod
from .fetcher import (
    fetch_all_shares,
    load_stock_list,
    resolve_markets_and_data,
)
from .backtest import backtest_symbol, summarize_trades
from .holdings import analyze_holding, load_holdings
from .market import classify_market
from .report import build_dataframes
from .scoring import analyze_stock
from .sensitivity import sensitivity_scan

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
    emit("抓股數", 0.78, "完成")

    market_state = None
    if cfg.get("market_filter", {}).get("enabled", True):
        emit("大盤判斷", 0.80, "抓 ^TWII 判斷大盤狀態")
        market_state = classify_market(
            cfg["data"]["period"], cfg["data"]["cache_dir"],
        )
        emit("大盤判斷", 0.81, f"{market_state['label']} — {market_state['detail']}")

    emit("分析", 0.82, f"逐檔分析 {len(resolved)} 檔")
    results = []
    failed_list = []
    total = max(len(resolved), 1)
    for i, r in enumerate(resolved):
        try:
            res = analyze_stock(
                r["symbol"], r["company_name"], r["market"],
                r["df"], shares_map.get(r["symbol"]), cfg,
                market_state=market_state,
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
            "錯誤訊息": "無法判斷上市/上櫃",
        })

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
    holdings: 直接傳 list[{code, company_name, entry_price, entry_date, lots}]
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
        r = code_to_resolved.get(h["code"])
        if r is None:
            rows.append({
                "股票": h["code"], "公司名稱": h["company_name"], "市場": None,
                "進場日": str(h["entry_date"]) if h["entry_date"] else None,
                "持有天數": None, "進場價": h["entry_price"],
                "目前價": None, "報酬%": None, "R倍數": None,
                "持有張數": h["lots"],
                "操作建議": "❓ 找不到資料", "賣出張數": "—",
                "說明": "市場未定位", "狀態": "找不到",
            })
            continue
        row = analyze_holding(
            r["symbol"], r["company_name"] or h["company_name"], r["market"],
            r["df"], h["entry_price"], h["entry_date"], h["lots"],
        )
        rows.append(row)

    df_h = pd.DataFrame(rows)
    emit("完成", 1.0, f"持股分析完成 {len(df_h)} 檔")
    return {"df": df_h}


def run_backtest(input_path, cfg, lookback_days=120, hold_days=10,
                 min_score=None, items=None, progress_cb=None):
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
    if min_score is None:
        min_score = cfg["scoring"]["thresholds"]["strong"]

    emit("回測", 0.55, f"逐檔回測 (min_score={min_score}, hold={hold_days}, lookback={lookback_days})")

    all_trades = []
    by_symbol = []
    total = max(len(resolved), 1)
    for i, r in enumerate(resolved):
        try:
            trades = backtest_symbol(
                r["df"], weights, min_score,
                hold_days=hold_days, lookback=lookback_days,
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

    summary = summarize_trades(all_trades)
    by_symbol_df = pd.DataFrame(by_symbol).sort_values(
        by="期望值R", ascending=False,
    ) if by_symbol else pd.DataFrame()

    emit("完成", 1.0, f"回測完成：{summary['總交易數']} 筆交易，勝率 {summary['勝率%']}%")
    return {
        "trades": trades_df,
        "summary": summary,
        "by_symbol": by_symbol_df,
        "resolved": resolved,
    }


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
