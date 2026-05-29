"""可重用掃描流程：CLI 與 GUI 共用"""
import logging
import time

from . import cache as cache_mod
from .fetcher import (
    fetch_all_shares,
    load_stock_list,
    resolve_markets_and_data,
)
from .report import build_dataframes
from .scoring import analyze_stock

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
    emit("抓股數", 0.80, "完成")

    emit("分析", 0.82, f"逐檔分析 {len(resolved)} 檔")
    results = []
    failed_list = []
    total = max(len(resolved), 1)
    for i, r in enumerate(resolved):
        try:
            res = analyze_stock(
                r["symbol"], r["company_name"], r["market"],
                r["df"], shares_map.get(r["symbol"]), cfg,
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

    return {
        "df": df,
        "summary": summary,
        "failed_df": failed_df,
        "elapsed_sec": elapsed,
    }
