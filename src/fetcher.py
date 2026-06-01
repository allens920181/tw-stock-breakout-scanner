import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yfinance as yf

from . import cache

log = logging.getLogger(__name__)


def fix_stock_code(code, etf_fix_map):
    if pd.isna(code):
        return None
    code = str(code).strip().replace(".0", "")
    if code == "" or code.lower() == "nan":
        return None
    if code in etf_fix_map:
        return etf_fix_map[code]
    if code.isdigit() and len(code) < 4:
        code = code.zfill(4)
    return code


def load_stock_list(file_path, etf_fix_map):
    df = pd.read_excel(file_path)
    items = []
    for _, row in df.iterrows():
        code = fix_stock_code(row["股票代號"], etf_fix_map)
        if code is None:
            continue
        items.append({
            "code": code,
            "company_name": str(row["公司名稱"]).strip(),
        })
    return items


def _split_multi(df_multi, symbols):
    out = {}
    if df_multi is None or df_multi.empty:
        return out
    if isinstance(df_multi.columns, pd.MultiIndex):
        tickers = df_multi.columns.get_level_values(0).unique()
        for t in tickers:
            sub = df_multi[t].dropna(how="all")
            if not sub.empty:
                out[t] = sub
    else:
        sub = df_multi.dropna(how="all")
        if not sub.empty and len(symbols) == 1:
            out[symbols[0]] = sub
    return out


def batch_download(symbols, period, chunk_size=50, sleep_between=1.0, progress_cb=None):
    """
    分批下載避免被 Yahoo rate-limit。
    progress_cb(done, total) — 可選回呼
    """
    if not symbols:
        return {}

    result = {}
    total = len(symbols)
    for i in range(0, total, chunk_size):
        chunk = symbols[i:i + chunk_size]
        try:
            df = yf.download(
                tickers=chunk,
                period=period,
                interval="1d",
                auto_adjust=False,
                progress=False,
                group_by="ticker",
                threads=True,
            )
            result.update(_split_multi(df, chunk))
        except Exception as e:
            log.warning("批次下載失敗（%d~%d）：%s", i, i + len(chunk), e)

        done = min(i + chunk_size, total)
        log.info("批次下載進度 %d/%d", done, total)
        if progress_cb:
            try:
                progress_cb(done, total)
            except Exception:
                pass

        if i + chunk_size < total:
            time.sleep(sleep_between)

    return result


def resolve_markets_and_data(items, period, cache_dir, chunk_size=50, chunk_sleep=1.0):
    """
    僅處理上市（.TW）；上櫃不納入。
    回傳 (resolved, not_found)
      resolved: list[{symbol, company_name, market, df}]
      not_found: list[(code, name)]
    """
    resolved = []
    pending_tw = []

    for it in items:
        code = it["code"]
        sym = code + ".TW"
        cached = cache.load_df(cache_dir, sym, "ohlc")
        if cached is not None and not cached.empty:
            resolved.append({
                "symbol": sym, "company_name": it["company_name"],
                "market": "TW", "df": cached,
            })
        else:
            pending_tw.append((sym, it["company_name"], code))

    log.info("批次下載 .TW %d 檔", len(pending_tw))
    tw_symbols = [x[0] for x in pending_tw]
    tw_data = batch_download(tw_symbols, period, chunk_size, chunk_sleep)

    not_found = []
    for sym, name, code in pending_tw:
        df = tw_data.get(sym)
        if df is not None and not df.empty:
            cache.save_df(cache_dir, sym, "ohlc", df)
            resolved.append({
                "symbol": sym, "company_name": name,
                "market": "TW", "df": df,
            })
        else:
            not_found.append((code, name))

    for code, name in not_found:
        log.warning("上市查無資料（非上市或代碼錯誤）：%s %s", code, name)

    return resolved, not_found


def _fetch_shares_one(symbol, cache_dir, retries=2):
    key = f"shares_{symbol.replace('.', '_')}"
    cached = cache.load_obj(cache_dir, key)
    if cached is not None:
        return symbol, cached

    val = None
    for i in range(retries + 1):
        try:
            t = yf.Ticker(symbol)

            # 優先 fast_info
            try:
                fi = t.fast_info
                v = None
                if hasattr(fi, "shares"):
                    v = fi.shares
                elif hasattr(fi, "get"):
                    v = fi.get("shares")
                if v:
                    val = v
                    break
            except Exception:
                pass

            # 次選 get_shares_full() 取最近一筆
            try:
                sf = t.get_shares_full()
                if sf is not None and len(sf) > 0:
                    val = float(sf.iloc[-1])
                    break
            except Exception:
                pass

            # 最後 fallback：info
            try:
                info = t.info or {}
                v = info.get("sharesOutstanding")
                if v:
                    val = v
                    break
            except Exception:
                pass

        except Exception:
            pass
        time.sleep(0.5 * (i + 1))

    cache.save_obj(cache_dir, key, val)
    return symbol, val


def _fetch_current_price_one(symbol):
    try:
        t = yf.Ticker(symbol)
        try:
            fi = t.fast_info
            v = None
            if hasattr(fi, "last_price"):
                v = fi.last_price
            elif hasattr(fi, "get"):
                v = fi.get("last_price") or fi.get("lastPrice")
            if v:
                return symbol, float(v)
        except Exception:
            pass
        try:
            hist = t.history(period="1d", interval="1m")
            if hist is not None and not hist.empty:
                return symbol, float(hist["Close"].iloc[-1])
        except Exception:
            pass
    except Exception:
        pass
    return symbol, None


def fetch_all_current_prices(symbols, max_workers):
    """並行抓即時/最新成交價（不快取，每次掃描都重抓）"""
    out = {}
    log.info("平行抓現價 %d 檔 (%d 緒)", len(symbols), max_workers)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_fetch_current_price_one, s) for s in symbols]
        for fu in as_completed(futures):
            try:
                sym, val = fu.result()
                out[sym] = val
            except Exception as e:
                log.warning("抓現價失敗：%s", e)
    return out


def fetch_all_shares(symbols, cache_dir, max_workers):
    out = {}
    log.info("平行抓股數 %d 檔 (%d 緒)", len(symbols), max_workers)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_fetch_shares_one, s, cache_dir) for s in symbols]
        for fu in as_completed(futures):
            try:
                sym, val = fu.result()
                out[sym] = val
            except Exception as e:
                log.warning("抓股數失敗：%s", e)
    return out
