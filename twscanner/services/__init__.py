"""
應用服務層（use cases）：把 data / strategy / market / research 組裝成完整流程。

GUI（twscanner.ui）與 CLI（twscanner.cli）都只呼叫這一層，不直接碰底層細節。
每個流程都接受可選的 progress_cb，方便不同介面顯示進度。
"""
from twscanner.services.holdings import run_holdings_scan
from twscanner.services.lookup import run_single_lookup
from twscanner.services.research import (
    run_adaptive_recommend,
    run_backtest,
    run_evaluate_journal,
    run_factor_eval,
    run_plateau,
    run_sensitivity,
    run_stress_test,
    run_weight_suggest,
)
from twscanner.services.scan import run_scan

__all__ = [
    "run_scan", "run_single_lookup", "run_holdings_scan",
    "run_backtest", "run_factor_eval", "run_weight_suggest", "run_evaluate_journal",
    "run_stress_test", "run_adaptive_recommend", "run_plateau", "run_sensitivity",
]
