import argparse
import logging
import sys

from src.config import load_config
from src.report import write_excel
from src.runner import run_scan


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
    p.add_argument("--min-score", type=int, default=None)
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument("--log-file", default=None)
    return p.parse_args()


def main():
    args = parse_args()
    setup_logging(args.log_level, args.log_file)

    cfg = load_config(args.config)
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
