import os
import pickle
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date

import pandas as pd
import yfinance as yf

# =====================================================
# 使用者設定
# =====================================================

stock_file = "stock_list.xlsx"
CACHE_DIR = ".cache"
MAX_WORKERS = 8
PERIOD = "1y"

os.makedirs(CACHE_DIR, exist_ok=True)


# =====================================================
# 本地快取（Parquet；失敗自動退回 pickle）
# 同一個交易日不重複下載
# =====================================================

def _cache_path(symbol, kind):
    today = date.today().strftime("%Y%m%d")
    safe = symbol.replace(".", "_")
    ext = "parquet" if kind == "ohlc" else "pkl"
    return os.path.join(CACHE_DIR, f"{safe}_{kind}_{today}.{ext}")


def cache_load_df(symbol, kind):
    path = _cache_path(symbol, kind)
    if not os.path.exists(path):
        return None
    try:
        if path.endswith(".parquet"):
            return pd.read_parquet(path)
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def cache_save_df(symbol, kind, df):
    path = _cache_path(symbol, kind)
    try:
        if path.endswith(".parquet"):
            df.to_parquet(path)
        else:
            with open(path, "wb") as f:
                pickle.dump(df, f)
    except Exception:
        # parquet 套件不存在時退回 pickle
        alt = path.replace(".parquet", ".pkl")
        with open(alt, "wb") as f:
            pickle.dump(df, f)


def cache_load_obj(key):
    path = os.path.join(CACHE_DIR, f"{key}_{date.today():%Y%m%d}.pkl")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def cache_save_obj(key, obj):
    path = os.path.join(CACHE_DIR, f"{key}_{date.today():%Y%m%d}.pkl")
    with open(path, "wb") as f:
        pickle.dump(obj, f)


# =====================================================
# 讀取股票清單
# =====================================================

def fix_stock_code(code):
    if pd.isna(code):
        return None

    code = str(code).strip().replace(".0", "")

    if code == "" or code.lower() == "nan":
        return None

    etf_fix_map = {
        "9805": "009805",
        "899": "00899",
        "902": "00902",
        "9819": "009819",
        "920": "00920",
    }

    if code in etf_fix_map:
        return etf_fix_map[code]

    if code.isdigit() and len(code) < 4:
        code = code.zfill(4)

    return code


def load_raw_stock_list(file_path):
    df = pd.read_excel(file_path)
    items = []
    for _, row in df.iterrows():
        code = fix_stock_code(row["股票代號"])
        if code is None:
            continue
        items.append({
            "code": code,
            "company_name": str(row["公司名稱"]).strip(),
        })
    return items


# =====================================================
# 批次下載 1 年日線
# 一次抓所有 .TW，把空的改抓 .TWO
# =====================================================

def _split_multi(df_multi):
    """yf.download(group_by='ticker') 結果 → {symbol: df}"""
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
        # 只剩一檔時 yfinance 會把 ticker 層省略
        out["__single__"] = df_multi.dropna(how="all")
    return out


def batch_download(symbols, period=PERIOD):
    if not symbols:
        return {}
    df = yf.download(
        tickers=symbols,
        period=period,
        interval="1d",
        auto_adjust=False,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    result = _split_multi(df)

    # 單檔情況補回 symbol key
    if "__single__" in result and len(symbols) == 1:
        result[symbols[0]] = result.pop("__single__")

    return result


def resolve_markets_and_data(items):
    """
    回傳 list[dict]：{symbol, company_name, market, df}
    步驟：
      1. 先試 .TW 批次抓
      2. 沒抓到的改試 .TWO
    全程經 cache 過濾，已快取的不重抓
    """
    # 階段 A：分離已快取 / 待抓
    pending_tw = []
    pending_two_map = {}  # code → company_name
    resolved = []

    for it in items:
        code = it["code"]
        # 嘗試從快取讀
        for suffix, market in [(".TW", "TW"), (".TWO", "TWO")]:
            sym = code + suffix
            cached = cache_load_df(sym, "ohlc")
            if cached is not None and not cached.empty:
                resolved.append({
                    "symbol": sym,
                    "company_name": it["company_name"],
                    "market": market,
                    "df": cached,
                })
                break
        else:
            pending_tw.append((code + ".TW", it["company_name"], code))

    # 階段 B：批次抓 .TW
    print(f"批次下載 .TW {len(pending_tw)} 檔 ...")
    tw_symbols = [x[0] for x in pending_tw]
    tw_data = batch_download(tw_symbols) if tw_symbols else {}

    for sym, name, code in pending_tw:
        df = tw_data.get(sym)
        if df is not None and not df.empty:
            cache_save_df(sym, "ohlc", df)
            resolved.append({
                "symbol": sym,
                "company_name": name,
                "market": "TW",
                "df": df,
            })
        else:
            pending_two_map[code] = name

    # 階段 C：批次抓 .TWO
    print(f"批次下載 .TWO {len(pending_two_map)} 檔 ...")
    two_symbols = [c + ".TWO" for c in pending_two_map]
    two_data = batch_download(two_symbols) if two_symbols else {}

    not_found = []
    for code, name in pending_two_map.items():
        sym = code + ".TWO"
        df = two_data.get(sym)
        if df is not None and not df.empty:
            cache_save_df(sym, "ohlc", df)
            resolved.append({
                "symbol": sym,
                "company_name": name,
                "market": "TWO",
                "df": df,
            })
        else:
            not_found.append((code, name))

    for code, name in not_found:
        print(code, name, "無法判斷上市/上櫃")

    return resolved, not_found


# =====================================================
# 平行抓股數（含快取）
# =====================================================

def _fetch_shares_one(symbol, retries=2):
    cached = cache_load_obj(f"shares_{symbol.replace('.', '_')}")
    if cached is not None:
        return symbol, cached

    last_val = None
    for i in range(retries + 1):
        try:
            t = yf.Ticker(symbol)
            # fast_info 較穩；失敗再 fallback info
            try:
                fi = t.fast_info
                last_val = getattr(fi, "shares", None) or fi.get("shares") if hasattr(fi, "get") else getattr(fi, "shares", None)
            except Exception:
                last_val = None

            if not last_val:
                info = t.info or {}
                last_val = info.get("sharesOutstanding")

            if last_val:
                break
        except Exception:
            pass
        time.sleep(0.5 * (i + 1))

    cache_save_obj(f"shares_{symbol.replace('.', '_')}", last_val)
    return symbol, last_val


def fetch_all_shares(symbols, max_workers=MAX_WORKERS):
    out = {}
    print(f"平行抓股數 {len(symbols)} 檔（{max_workers} 緒）...")
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_fetch_shares_one, s) for s in symbols]
        for fu in as_completed(futures):
            try:
                sym, val = fu.result()
                out[sym] = val
            except Exception:
                pass
    return out


# =====================================================
# 技術指標
# =====================================================

def add_indicators(df):
    df = df.copy()
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()

    low = df["Low"].rolling(9).min()
    high = df["High"].rolling(9).max()
    rsv = (df["Close"] - low) / (high - low) * 100

    df["K"] = rsv.ewm(com=2).mean()
    df["D"] = df["K"].ewm(com=2).mean()

    ema12 = df["Close"].ewm(span=12).mean()
    ema26 = df["Close"].ewm(span=26).mean()

    df["DIF"] = ema12 - ema26
    df["MACD"] = df["DIF"].ewm(span=9).mean()
    df["OSC"] = df["DIF"] - df["MACD"]

    return df


# =====================================================
# 單檔股票分析（吃已下載好的 df 與 shares）
# =====================================================

def analyze_stock(symbol, company_name, market, df, shares):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if df.empty or len(df) < 80:
        return {
            "股票": symbol, "公司名稱": company_name, "市場": market,
            "狀態": "資料不足", "訊號判斷": "無法分析",
            "評分": 0, "換手率%": None, "RR比": None,
        }

    df = add_indicators(df).dropna()

    if len(df) < 30:
        return {
            "股票": symbol, "公司名稱": company_name, "市場": market,
            "狀態": "指標資料不足", "訊號判斷": "無法分析",
            "評分": 0, "換手率%": None, "RR比": None,
        }

    latest = df.iloc[-1]
    high_20 = df["High"].iloc[-21:-1].max()
    vol20 = df["Volume"].rolling(20).mean().iloc[-1]

    if shares is not None and shares > 0:
        turnover_rate = latest["Volume"] / shares * 100
        avg_turnover_20 = vol20 / shares * 100
    else:
        turnover_rate = None
        avg_turnover_20 = None

    ma = latest["MA5"] > latest["MA20"] > latest["MA60"]
    ma20_base = latest["Close"] > latest["MA20"]
    kd = latest["K"] > latest["D"] and latest["K"] > 70
    macd = latest["OSC"] > 0
    breakout = latest["Close"] > high_20
    vol_ok = latest["Volume"] > vol20 * 1.2

    if turnover_rate is not None:
        turnover_ok = turnover_rate > 1
        turnover_strong = turnover_rate > avg_turnover_20
    else:
        turnover_ok = False
        turnover_strong = False

    score = sum([ma, ma20_base, kd, macd, breakout, vol_ok, turnover_ok, turnover_strong])

    entry = latest["Close"]
    stop1 = latest["MA20"]
    stop2 = df["Low"].iloc[-10:].min()
    stop = max(stop1, stop2)
    risk = entry - stop

    if risk > 0:
        target = entry + 2 * risk
        rr = (target - entry) / (entry - stop)
    else:
        target = None
        rr = None

    if score >= 6:
        signal = "強勢候選"
    elif score >= 5:
        signal = "觀察"
    elif score >= 4:
        signal = "偏弱觀察"
    else:
        signal = "不符合"

    return {
        "股票": symbol, "公司名稱": company_name, "市場": market,
        "狀態": "成功", "訊號判斷": signal, "評分": score,

        "收盤價": round(entry, 2),
        "進場參考價": round(entry, 2),
        "停損價": round(stop, 2),
        "目標價": round(target, 2) if target is not None else None,
        "風險": round(risk, 2),
        "RR比": round(rr, 2) if rr is not None else None,

        "MA5": round(latest["MA5"], 2),
        "MA20": round(latest["MA20"], 2),
        "MA60": round(latest["MA60"], 2),

        "K": round(latest["K"], 2),
        "D": round(latest["D"], 2),
        "OSC": round(latest["OSC"], 2),

        "20日高點": round(high_20, 2),
        "成交量": int(latest["Volume"]),
        "20日均量": int(vol20),

        "流通股數近似值": int(shares) if shares is not None else None,
        "換手率%": round(turnover_rate, 2) if turnover_rate is not None else None,
        "20日平均換手率%": round(avg_turnover_20, 2) if avg_turnover_20 is not None else None,

        "MA多頭排列": ma,
        "站上MA20": ma20_base,
        "KD強勢": kd,
        "MACD多方": macd,
        "突破20日高點": breakout,
        "成交量放大": vol_ok,
        "換手率大於1%": turnover_ok,
        "換手率大於20日平均": turnover_strong,
    }


# =====================================================
# 主流程
# =====================================================

def main():
    t0 = time.time()

    items = load_raw_stock_list(stock_file)
    print(f"讀入 {len(items)} 檔股票")

    resolved, not_found = resolve_markets_and_data(items)
    print(f"成功定位 {len(resolved)} 檔，{len(not_found)} 檔找不到市場")

    symbols = [r["symbol"] for r in resolved]
    shares_map = fetch_all_shares(symbols)

    print("開始分析 ...")
    results = []
    failed_list = []
    for r in resolved:
        try:
            res = analyze_stock(
                r["symbol"], r["company_name"], r["market"],
                r["df"], shares_map.get(r["symbol"]),
            )
            results.append(res)
        except Exception as e:
            print(r["symbol"], r["company_name"], "錯誤：", e)
            failed_list.append({
                "股票": r["symbol"],
                "公司名稱": r["company_name"],
                "市場": r["market"],
                "錯誤訊息": str(e),
            })

    for code, name in not_found:
        failed_list.append({
            "股票": code, "公司名稱": name, "市場": None,
            "錯誤訊息": "無法判斷上市/上櫃",
        })

    df = pd.DataFrame(results)
    for col in ["評分", "換手率%", "RR比"]:
        if col not in df.columns:
            df[col] = None

    df = df.sort_values(
        by=["評分", "換手率%", "RR比"],
        ascending=[False, False, False],
        na_position="last",
    )

    summary = pd.DataFrame([{
        "掃描股票數": len(items),
        "成功分析檔數": len(df[df["狀態"] == "成功"]) if "狀態" in df.columns else 0,
        "強勢候選檔數": len(df[df["訊號判斷"] == "強勢候選"]) if "訊號判斷" in df.columns else 0,
        "觀察檔數": len(df[df["訊號判斷"] == "觀察"]) if "訊號判斷" in df.columns else 0,
        "偏弱觀察檔數": len(df[df["訊號判斷"] == "偏弱觀察"]) if "訊號判斷" in df.columns else 0,
        "不符合檔數": len(df[df["訊號判斷"] == "不符合"]) if "訊號判斷" in df.columns else 0,
        "執行秒數": round(time.time() - t0, 1),
        "策略條件": "突破 + KD + MACD + 成交量 + 換手率 + MA20基準",
        "說明": "v3 優化：批次下載 + 平行抓股數 + 本地快取（同日不重抓）",
    }])

    failed_df = pd.DataFrame(failed_list)

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"台股全部分析報告_自動判斷市場_{now}.xlsx"

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="全部分析結果", index=False)
        summary.to_excel(writer, sheet_name="Report摘要", index=False)
        if len(failed_df) > 0:
            failed_df.to_excel(writer, sheet_name="錯誤清單", index=False)

    print(df)
    print(f"Excel Report 已輸出：{output_file}")
    print(f"總耗時 {time.time() - t0:.1f} 秒")


if __name__ == "__main__":
    main()
