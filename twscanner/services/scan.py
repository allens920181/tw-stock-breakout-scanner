"""買入掃描流程（GUI / CLI 共用）：下載 → 籌碼/營收/產業 → 評分 → 族群熱度 → 輸出"""
import logging
import time

from twscanner.core import cache as cache_mod
from twscanner.data.chips import fetch_chips
from twscanner.data.earnings import fetch_all_earnings
from twscanner.data.margin import fetch_margin
from twscanner.data.prices import (
    fetch_all_current_prices,
    fetch_all_shares,
    load_stock_list,
    resolve_markets_and_data,
)
from twscanner.data.revenue import fetch_revenue
from twscanner.data.sectors import fetch_sectors, fetch_shares_official
from twscanner.market.tw_regime import classify_market
from twscanner.market.us_regime import classify_us_market, merge_position_factor
from twscanner.reporting.excel import build_dataframes
from twscanner.strategy.ambush import analyze_ambush
from twscanner.strategy.groups import annotate_group_strength, apply_sector_heat
from twscanner.strategy.scoring import analyze_stock

log = logging.getLogger(__name__)


def run_scan(input_path=None, cfg=None, progress_cb=None, items=None, cached=None):
    """
    progress_cb(stage: str, pct: float, message: str) — 可選回呼
    items: 可選；直接傳入 [{code, company_name}] 跳過 Excel 讀取
    cached: 可選；傳入先前掃描的資料（resolved/各 map/market_state）→ 跳過所有下載，
            只重跑分析（換風格 Preset / 策略模式時即時重評估，免重抓）

    Returns: dict 含 df / summary / failed_df / elapsed_sec / 以及可快取的原始資料
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

    if cached is not None:
        # ===== 重評估模式：直接用快取資料，不下載 =====
        emit("重新評估", 0.5, "用現有資料重新分析（免重抓）")
        items = cached["items"]
        resolved = cached["resolved"]
        not_found = cached.get("not_found", [])
        shares_map = cached["shares_map"]
        price_map = cached["price_map"]
        chips_map = cached["chips_map"]
        margin_map = cached["margin_map"]
        earnings_map = cached["earnings_map"]
        revenue_map = cached.get("revenue_map", {})
        market_state = cached["market_state"]
        symbols = [r["symbol"] for r in resolved]
    else:
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

        emit("抓股數", 0.55, f"取流通股數 {len(resolved)} 檔（TWSE 官方優先）")
        symbols = [r["symbol"] for r in resolved]
        # 主來源：TWSE 官方流通股數（雲端不被擋，解決換手率空白）
        official_shares = {}
        try:
            official_shares = fetch_shares_official(
                cfg["data"]["cache_dir"],
                verify=cfg.get("sectors", {}).get("verify_ssl", True),
            )
        except Exception as e:
            log.warning("官方流通股數抓取失敗，改用 yfinance：%s", e)
        # 備援：官方查無的（少數 ETF/特殊代號）才動用 yfinance
        missing = [s for s in symbols if s.split(".")[0] not in official_shares]
        yf_shares = {}
        if missing:
            yf_shares = fetch_all_shares(
                missing, cfg["data"]["cache_dir"], cfg["data"]["max_workers"],
            )
        shares_map = {}
        for s in symbols:
            code = s.split(".")[0]
            shares_map[s] = official_shares.get(code) or yf_shares.get(s)
        emit("抓股數", 0.76, f"官方 {len(official_shares)} 檔 + yfinance 補 {len(missing)} 檔")

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

        revenue_map = {}
        rev_cfg = cfg.get("revenue", {})
        if rev_cfg.get("enabled", True):
            emit("抓營收", 0.798, "抓月營收年增/月增")
            try:
                revenue_map = fetch_revenue(
                    cfg["data"]["cache_dir"], verify=rev_cfg.get("verify_ssl", True),
                )
                emit("抓營收", 0.799, f"月營收 {len(revenue_map)} 檔")
            except Exception as e:
                log.warning("月營收抓取失敗，略過：%s", e)

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

            # 大資金 / 宏觀資金面（外資台指期 / 台幣 / 大盤融資）
            big_state = None
            bm_cfg = cfg.get("bigmoney", {})
            if bm_cfg.get("enabled", True):
                emit("大盤判斷", 0.81, "抓大資金（外資台指期/台幣/大盤融資）")
                try:
                    from datetime import timedelta

                    from twscanner.core.tz import today_tw
                    from twscanner.market.bigmoney import classify_bigmoney
                    today = today_tw()
                    mdates = [(today - timedelta(days=k)).strftime("%Y%m%d")
                              for k in range(0, 9)]
                    big_state = classify_bigmoney(
                        cache_dir=cfg["data"]["cache_dir"],
                        verify=bm_cfg.get("verify_ssl", True),
                        margin_dates=mdates, weights=bm_cfg.get("weights"),
                    )
                    emit("大盤判斷", 0.815,
                         f"大資金 {big_state['label']} — {big_state['detail']}")
                except Exception as e:
                    log.warning("大資金判斷失敗，略過：%s", e)

            # 合併三因子：取較保守者
            combined_factor = merge_position_factor(market_state, us_state, big_state)
            if market_state:
                market_state["position_factor"] = combined_factor
                market_state["us_state"] = us_state
                market_state["big_state"] = big_state

    # 隨大盤切門檻（建議模式套用後）：依當前 regime 覆寫進場門檻 enter
    rg_thr = cfg.get("scoring", {}).get("regime_thresholds")
    if rg_thr and market_state and market_state.get("regime") in rg_thr:
        new_enter = rg_thr[market_state["regime"]]
        cfg["scoring"]["thresholds"]["enter"] = new_enter
        emit("分析", 0.815,
             f"依大盤（{market_state.get('regime')}）套用進場門檻 enter={new_enter}")

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
                revenue=revenue_map.get(r["symbol"].split(".")[0]),
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
        # 可快取的原始資料：之後換風格/模式時傳回 cached= 即可免重抓
        "scan_cache": {
            "items": items,
            "resolved": resolved,
            "not_found": not_found,
            "shares_map": shares_map,
            "price_map": price_map,
            "chips_map": chips_map,
            "margin_map": margin_map,
            "earnings_map": earnings_map,
            "revenue_map": revenue_map,
            "market_state": market_state,
        },
    }




# =====================================================================
# 當日資料池：換範圍時只補抓缺的股票
#   掃描會把下載到的原始資料（OHLC、股數、現價、財報日 + 全市場的籌碼/融資/營收/大盤）存成 scan_cache。
#   把多次掃描的 scan_cache 合併成「資料池」；換範圍時先從池子切出子集，缺的才下載。
#   例：先掃全台股，再換「僅普通股」或上傳自選清單 → 0 檔要下載，幾秒內重算完成。
# =====================================================================
_SYMBOL_MAPS = ("shares_map", "price_map", "earnings_map")         # 以 2330.TW 為 key
_MARKET_DATA = ("chips_map", "margin_map", "revenue_map", "market_state")   # 全市場一份


def _code(symbol):
    return str(symbol).split(".")[0]


def split_by_pool(pool, items):
    """
    items（[{code, company_name}]）對照資料池。
    回 (子集 cache 或 None, 需要補抓的 items)。子集可直接傳給 run_scan(cached=...)。
    池子裡查無資料（not_found）的代號不會再抓一次。
    """
    items = list(items)
    if not pool:
        return None, items
    have = {_code(r["symbol"]): r for r in pool.get("resolved", [])}
    nf = dict(pool.get("not_found", []))
    missing = [it for it in items if it["code"] not in have and it["code"] not in nf]
    resolved = [have[it["code"]] for it in items if it["code"] in have]
    syms = {r["symbol"] for r in resolved}
    sub = {k: pool.get(k) for k in _MARKET_DATA}
    sub["items"] = items
    sub["resolved"] = resolved
    sub["not_found"] = [(it["code"], it["company_name"]) for it in items if it["code"] in nf]
    for k in _SYMBOL_MAPS:
        sub[k] = {s: v for s, v in (pool.get(k) or {}).items() if s in syms}
    return sub, missing


def merge_pool(pool, cache):
    """把新掃描的 scan_cache 併入資料池（同代號以新資料為準；全市場資料用較新的一份）。"""
    if not pool:
        return {**cache, "resolved": list(cache.get("resolved", [])), "not_found": list(cache.get("not_found", []))}
    resolved = {r["symbol"]: r for r in pool.get("resolved", [])}
    resolved.update({r["symbol"]: r for r in cache.get("resolved", [])})
    got = {_code(s) for s in resolved}
    nf = dict(pool.get("not_found", []))
    nf.update(dict(cache.get("not_found", [])))
    items = {it["code"]: it for it in pool.get("items", [])}
    items.update({it["code"]: it for it in cache.get("items", [])})
    out = {"items": list(items.values()), "resolved": list(resolved.values()),
           "not_found": [(c, n) for c, n in nf.items() if c not in got]}
    for k in _SYMBOL_MAPS:
        out[k] = {**(pool.get(k) or {}), **(cache.get(k) or {})}
    for k in _MARKET_DATA:
        out[k] = cache.get(k) if cache.get(k) is not None else pool.get(k)
    return out


def refresh_prices(cache, cfg):
    """只重抓子集的即時現價（追高判斷用），回新的 price_map。價格歷史與其他資料不動。"""
    syms = [r["symbol"] for r in cache.get("resolved", [])]
    fresh = fetch_all_current_prices(syms, cfg["data"]["max_workers"]) if syms else {}
    return {**(cache.get("price_map") or {}), **{s: v for s, v in fresh.items() if v is not None}}
