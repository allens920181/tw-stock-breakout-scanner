import argparse
import logging
import sys

from src.config import load_config
from src.report import write_excel
from src.runner import run_backtest, run_scan
from src.universe import fetch_twse_universe


def setup_logging(level, log_file=None):
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=level, format=fmt, handlers=handlers, force=True)


def parse_args():
    p = argparse.ArgumentParser(description="台股強勢突破交易清單掃描器")
    p.add_argument("--input", "-i", default="stock_list.xlsx")
    p.add_argument("--config", "-c", default="config.yaml")
    p.add_argument("--universe", choices=["twse", "twse-common", "twse-etf"],
                   default=None,
                   help="掃描全台股：twse=上市+ETF, twse-common=僅普通股, twse-etf=僅ETF")
    p.add_argument("--min-score", type=int, default=None)
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument("--log-file", default=None)

    p.add_argument("--backtest", action="store_true",
                   help="走 walk-forward 回測，不做即時掃描")
    p.add_argument("--lookback-days", type=int, default=120)
    p.add_argument("--hold-days", type=int, default=10)
    return p.parse_args()


def main():
    args = parse_args()
    setup_logging(args.log_level, args.log_file)

    cfg = load_config(args.config)

    if args.backtest:
        items = None
        if args.universe:
            include_common = args.universe in ("twse", "twse-common")
            include_etf = args.universe in ("twse", "twse-etf")
            uni = fetch_twse_universe(include_common, include_etf)
            items = [{"code": x["code"], "company_name": x["company_name"]} for x in uni]
        bt = run_backtest(
            args.input, cfg,
            lookback_days=args.lookback_days,
            hold_days=args.hold_days,
            min_score=args.min_score,
            items=items,
        )
        log_main = logging.getLogger("main")
        log_main.info("=== 回測摘要 ===")
        for k, v in bt["summary"].items():
            log_main.info("  %s: %s", k, v)

        import os
        from datetime import datetime
        out_dir = cfg["output"]["dir"]
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(out_dir, f"回測報告_{ts}.xlsx")
        import pandas as pd
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame([bt["summary"]]).to_excel(writer, sheet_name="摘要", index=False)
            if len(bt["trades"]):
                bt["trades"].to_excel(writer, sheet_name="交易明細", index=False)
            if len(bt["by_symbol"]):
                bt["by_symbol"].to_excel(writer, sheet_name="個股統計", index=False)
        log_main.info("回測報告已輸出：%s", path)
        return

    if args.universe:
        include_common = args.universe in ("twse", "twse-common")
        include_etf = args.universe in ("twse", "twse-etf")
        items = fetch_twse_universe(
            include_common=include_common, include_etf=include_etf,
        )
        items = [{"code": x["code"], "company_name": x["company_name"]} for x in items]
        result = run_scan(cfg=cfg, items=items)
    else:
        result = run_scan(args.input, cfg)

    df = result["df"]
    if args.min_score is not None:
        df = df[df["評分"] >= args.min_score]

    out_cfg = cfg["output"]
    path = write_excel(df, result["summary"], result["failed_df"],
                       out_cfg["dir"], out_cfg["prefix"])

    logging.getLogger("main").info("Excel 已輸出：%s", path)


if __name__ == "__main__":
    main()
