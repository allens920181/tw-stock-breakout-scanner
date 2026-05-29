import argparse
import logging
import sys
import time

from src import cache as cache_mod
from src.config import load_config
from src.fetcher import (
    fetch_all_shares,
    load_stock_list,
    resolve_markets_and_data,
)
from src.report import build_dataframes, write_excel
from src.scoring import analyze_stock


def setup_logging(level, log_file=None):
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=level, format=fmt, handlers=handlers, force=True)


def parse_args():
    p = argparse.ArgumentParser(description="台股強勢突破交易清單掃描器")
    p.add_argument("--input", "-i", default="stock_list.xlsx", help="股票清單 Excel")
    p.add_argument("--config", "-c", default="config.yaml", help="設定檔路徑")
    p.add_argument("--min-score", type=int, default=None,
                   help="只輸出評分 ≥ 此值的結果（不指定則輸出全部）")
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument("--log-file", default=None, help="同步寫入 log 檔（選填）")
    return p.parse_args()


def main():
    args = parse_args()
    setup_logging(args.log_level, args.log_file)
    log = logging.getLogger("main")

    t0 = time.time()
    cfg = load_config(args.config)
    cache_mod.ensure_dir(cfg["data"]["cache_dir"])

    items = load_stock_list(args.input, cfg["etf_fix_map"])
    log.info("讀入 %d 檔股票", len(items))

    resolved, not_found = resolve_markets_and_data(
        items, cfg["data"]["period"], cfg["data"]["cache_dir"],
    )
    log.info("定位成功 %d 檔，無法判斷 %d 檔", len(resolved), len(not_found))

    symbols = [r["symbol"] for r in resolved]
    shares_map = fetch_all_shares(
        symbols, cfg["data"]["cache_dir"], cfg["data"]["max_workers"],
    )

    log.info("開始分析 ...")
    results = []
    failed_list = []
    for r in resolved:
        try:
            res = analyze_stock(
                r["symbol"], r["company_name"], r["market"],
                r["df"], shares_map.get(r["symbol"]), cfg,
            )
            results.append(res)
        except Exception as e:
            log.exception("分析失敗：%s %s", r["symbol"], r["company_name"])
            failed_list.append({
                "股票": r["symbol"], "公司名稱": r["company_name"],
                "市場": r["market"], "錯誤訊息": str(e),
            })

    for code, name in not_found:
        failed_list.append({
            "股票": code, "公司名稱": name, "市場": None,
            "錯誤訊息": "無法判斷上市/上櫃",
        })

    elapsed = time.time() - t0
    df, summary, failed_df = build_dataframes(results, failed_list, len(items), elapsed)

    if args.min_score is not None:
        df = df[df["評分"] >= args.min_score]
        log.info("套用 --min-score=%d，剩 %d 檔", args.min_score, len(df))

    out_cfg = cfg["output"]
    path = write_excel(df, summary, failed_df, out_cfg["dir"], out_cfg["prefix"])

    log.info("Excel 已輸出：%s", path)
    log.info("總耗時 %.1f 秒", elapsed)


if __name__ == "__main__":
    main()
