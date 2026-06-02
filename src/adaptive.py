# -*- coding: utf-8 -*-
"""
自適應參數建議（建議模式 / walk-forward）

把回測「回饋」到選股參數，但嚴守紀律：
  1. 只建議、不自動改 —— 由使用者一鍵套用（保留決策權）。
  2. 取「參數高原中心」而非最高峰 —— 避免追噪音/過擬合（reuse detect_plateau）。
  3. 每個建議都附 OOS 同向檢核 —— 樣本內(IS)決定、樣本外(OOS)只驗證；
     OOS 期望值與 IS 不同向 → 標記「未通過」，提醒別套用。

對象（依使用者選擇）：
  - 進場門檻 min_score / atr_mult / tp_mult（高原中心）
  - 評分權重 7 因子（因子 lift 建議，reuse suggest_weights_from_lift）
  - 隨大盤切整組門檻：同一 min_score 網格下，依進場日 regime 分桶，
    各 regime 取期望值最佳的 min_score（樣本不足則回退整體建議）。
"""
import logging

from .backtest import backtest_symbol, split_trades_is_oos, summarize_trades
from .factor_eval import evaluate_factors, suggest_weights_from_lift
from .sensitivity import detect_plateau

log = logging.getLogger(__name__)

_REGIMES = ["bull", "neutral", "bear"]
_REGIME_LABEL = {"bull": "多頭", "neutral": "中性/震盪", "bear": "空頭"}


def _expectancy(trades):
    s = summarize_trades(trades)
    return s.get("期望值R"), s.get("總交易數", 0)


def _oos_same_sign(trades, cfg, oos_ratio=0.3):
    """IS/OOS 期望值是否同向（且皆非負）→ 視為通過 walk-forward 檢核。"""
    if not trades:
        return None
    is_tr, oos_tr = split_trades_is_oos(trades, oos_ratio=oos_ratio, mode="ratio")
    if not is_tr or not oos_tr:
        return None
    is_e, _ = _expectancy(is_tr)
    oos_e, _ = _expectancy(oos_tr)
    if is_e is None or oos_e is None:
        return None
    return bool(is_e > 0 and oos_e > 0)


def _grid_backtest(resolved, cfg, *, min_score, lookback, hold_days,
                   stop_mode="ma", atr_mult=None, tp_mult=2.0, regime_map=None):
    weights = cfg["scoring"]["weights"]
    costs = cfg.get("costs")
    out = []
    for r in resolved:
        try:
            out.extend(backtest_symbol(
                r["df"], weights, min_score,
                hold_days=hold_days, lookback=lookback, costs=costs,
                stop_mode=stop_mode, atr_mult=atr_mult, tp_mult=tp_mult,
                regime_map=regime_map,
            ))
        except Exception:
            pass
    return out


def _recommend_one_param(resolved, cfg, param_name, grid, lookback, hold_days,
                         pcfg, collect_trades=False):
    """單參數高原中心建議 + OOS 檢核。回傳 (rec_dict, trades_by_value)。"""
    base_min_score = cfg["scoring"]["thresholds"].get("enter", 7)
    base_atr = cfg["filters"].get("atr_mult", 1.5)

    values, exps, trades_by_value = [], [], {}
    for val in grid:
        min_score, stop_mode, atr_mult, tp_mult = base_min_score, "ma", None, 2.0
        if param_name == "min_score":
            min_score = val
        elif param_name == "atr_mult":
            stop_mode, atr_mult = "atr", val
        elif param_name == "tp_mult":
            tp_mult, stop_mode, atr_mult = val, "atr", base_atr
        trades = _grid_backtest(
            resolved, cfg, min_score=min_score, lookback=lookback,
            hold_days=hold_days, stop_mode=stop_mode, atr_mult=atr_mult,
            tp_mult=tp_mult,
        )
        exp, _ = _expectancy(trades)
        values.append(val)
        exps.append(exp if exp is not None else float("nan"))
        if collect_trades:
            trades_by_value[val] = trades

    plateau = detect_plateau(
        values, exps,
        plateau_ratio=pcfg.get("plateau_ratio", 0.7),
        min_width=pcfg.get("min_width", 3),
        neighbor_w=pcfg.get("neighbor_w", 1),
        spike_drop=pcfg.get("spike_drop", 0.5),
    )
    rec = plateau.get("recommended")
    cur = {"min_score": base_min_score, "atr_mult": base_atr,
           "tp_mult": cfg.get("backtest", {}).get("tp_mult", 2.0)}.get(param_name)

    oos_ok = None
    if rec is not None and collect_trades:
        oos_ok = _oos_same_sign(trades_by_value.get(rec, []), cfg)
    return {
        "param": param_name, "current": cur, "recommended": rec,
        "has_plateau": plateau.get("plateau") is not None,
        "oos_ok": oos_ok, "curve": list(zip(values, exps)),
    }, trades_by_value


def recommend_regime_thresholds(resolved, cfg, grid, lookback, hold_days,
                                regime_map, min_n=20):
    """
    隨大盤切門檻：同一 min_score 網格，依進場日 regime 分桶，
    各 regime 取期望值最高（樣本 ≥ min_n）的 min_score；不足則回退整體建議。
    """
    by_regime_exp = {rg: {} for rg in _REGIMES}      # regime -> {score: (exp, n)}
    overall = {}                                     # score -> exp
    for val in grid:
        trades = _grid_backtest(
            resolved, cfg, min_score=val, lookback=lookback,
            hold_days=hold_days, regime_map=regime_map,
        )
        e_all, _ = _expectancy(trades)
        overall[val] = e_all if e_all is not None else float("-inf")
        buckets = {rg: [] for rg in _REGIMES}
        for t in trades:
            rg = t.get("regime")
            if rg in buckets:
                buckets[rg].append(t)
        for rg in _REGIMES:
            e, n = _expectancy(buckets[rg])
            by_regime_exp[rg][val] = (e if e is not None else float("-inf"), n)

    overall_best = max(overall, key=overall.get) if overall else None
    out = {}
    for rg in _REGIMES:
        cand = [(v, e, n) for v, (e, n) in by_regime_exp[rg].items() if n >= min_n]
        if cand:
            best = max(cand, key=lambda x: x[1])
            out[rg] = {"recommended": best[0], "expectancy": round(best[1], 3),
                       "n": best[2], "fallback": False}
        else:
            out[rg] = {"recommended": overall_best, "expectancy": None,
                       "n": sum(n for _, n in by_regime_exp[rg].values()),
                       "fallback": True}
    return {"overall_best": overall_best, "by_regime": out,
            "labels": _REGIME_LABEL}


def recommend_from_backtest(resolved, cfg, *, lookback=120, hold_days=10,
                            targets=("thresholds", "weights", "regime"),
                            fe_result=None, progress_cb=None):
    """
    產生「建議模式」完整建議包。targets 控制要算哪些對象（省算）。
    回傳 dict：{params:[...], weights:{...}, regime:{...}, note:str}
    """
    def emit(p, msg):
        if progress_cb:
            try:
                progress_cb(p, msg)
            except Exception:
                pass

    pcfg = cfg.get("sensitivity", {}).get("plateau", {})
    out = {"params": [], "weights": None, "regime": None, "note": ""}

    if "thresholds" in targets:
        grids = {
            "min_score": pcfg.get("min_score_grid", [4, 5, 6, 7, 8]),
            "atr_mult": pcfg.get("atr_mult_grid", [1.0, 1.5, 2.0, 2.5, 3.0]),
            "tp_mult": pcfg.get("tp_mult_grid", [1.5, 2.0, 2.5, 3.0]),
        }
        for i, (pname, grid) in enumerate(grids.items()):
            emit(0.05 + 0.45 * i / len(grids), f"高原掃描 {pname}")
            rec, _ = _recommend_one_param(
                resolved, cfg, pname, grid, lookback, hold_days, pcfg,
                collect_trades=True,
            )
            out["params"].append(rec)

    if "weights" in targets:
        emit(0.55, "因子 lift 建議權重")
        if fe_result is None:
            fe_result = evaluate_factors(resolved, cfg, lookback=lookback,
                                         hold_days=hold_days)
        lw = cfg.get("scoring", {}).get("lift_weights", {})
        sug = suggest_weights_from_lift(
            fe_result, cfg, total=lw.get("total", 8), eps=lw.get("eps", 0.02),
            preserve_unverifiable=lw.get("preserve_unverifiable", ["turnover_strong"]),
        )
        out["weights"] = {
            "current": dict(cfg["scoring"]["weights"]),
            "recommended": sug.get("weights"),
            "detail": sug.get("detail", []),
            "note": sug.get("note", ""),
        }

    if "regime" in targets:
        emit(0.8, "依大盤分桶建議門檻")
        try:
            from .market import build_regime_map
            regime_map = build_regime_map(cfg["data"]["period"], cfg["data"]["cache_dir"])
            grid = pcfg.get("min_score_grid", [4, 5, 6, 7, 8])
            out["regime"] = recommend_regime_thresholds(
                resolved, cfg, grid, lookback, hold_days, regime_map,
            )
        except Exception as e:
            log.warning("regime 建議失敗：%s", e)
            out["note"] += f"（regime 建議略過：{e}）"

    emit(1.0, "完成")
    return out
