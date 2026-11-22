"""
總經與市場序列（給「回升訊號」用）：只抓 + 解析，每天快取一次。

- fetch_close：yfinance 收盤價（^VIX、^SOX、NVDA …）
- fetch_fred：美國聯準會 FRED 公開 CSV（免 key）。SAHMREALTIME = Sahm 衰退指標、BAA10Y = Baa 公司債利差
- fetch_foreign_net：三大法人買賣金額中的外資（不含外資自營商）每日買賣超（億元），來源 FinMind 公開 API，
  與證交所 BFI82U 相同（2012–2013 年逐月核對一致）。一次請求拿到整段，不必逐日打證交所。
"""
import io
import logging
from datetime import datetime, timedelta

import pandas as pd
import requests
import yfinance as yf

from twscanner.core import cache as cache_mod
from twscanner.core.tz import today_tw

log = logging.getLogger(__name__)

_TIMEOUT = (6, 15)        # (連線, 讀取)：抓不到就放棄，不讓頁面卡住
_HEADERS = {"User-Agent": "Mozilla/5.0 (stock-scan)"}
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"


def fetch_close(symbol, cache_dir=".cache", period="1y"):
    """收盤價 Series（index=日期）。與 us_regime 共用同一份 ohlc 快取。"""
    df = cache_mod.load_df(cache_dir, symbol, "ohlc")
    if df is None or df.empty:
        df = yf.download(symbol, period=period, interval="1d", auto_adjust=False, progress=False)
        if df is None or df.empty:
            return None
        if hasattr(df.columns, "get_level_values"):
            try:
                df.columns = df.columns.get_level_values(0)
            except Exception:
                pass
        cache_mod.save_df(cache_dir, symbol, "ohlc", df)
    s = df["Close"].dropna()
    idx = pd.to_datetime(s.index)
    s.index = idx.tz_localize(None) if idx.tz is not None else idx
    return s


def parse_fred_csv(text):
    """FRED CSV（observation_date, 值）→ Series；'.' 代表缺值。"""
    df = pd.read_csv(io.StringIO(text))
    if df.shape[1] < 2:
        return None
    s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s.index = pd.to_datetime(df.iloc[:, 0])
    s = s.dropna()
    return s if len(s) else None


def fetch_fred(series_id, cache_dir=".cache"):
    key = f"fred_{series_id}"
    cached = cache_mod.load_obj(cache_dir, key)
    if cached is not None:
        return cached
    r = requests.get(FRED_URL, params={"id": series_id}, headers=_HEADERS, timeout=_TIMEOUT)
    r.raise_for_status()
    s = parse_fred_csv(r.text)
    if s is not None:
        cache_mod.ensure_dir(cache_dir)
        cache_mod.save_obj(cache_dir, key, s)
    return s


def parse_finmind_foreign(js):
    """FinMind TaiwanStockTotalInstitutionalInvestors → 外資（Foreign_Investor）每日買賣超（億元）。"""
    rows = [r for r in (js or {}).get("data") or [] if r.get("name") == "Foreign_Investor"]
    if not rows:
        return None
    s = pd.Series({pd.Timestamp(r["date"]): (float(r["buy"]) - float(r["sell"])) / 1e8 for r in rows})
    return s.sort_index()


FOREIGN_TTL = timedelta(hours=2)    # 法人資料下午 3 點後才公布：同一天也要能補上


def fetch_foreign_net(cache_dir=".cache", days=90):
    key = "foreign_net_total"
    cached = cache_mod.load_obj(cache_dir, key)
    if cached is not None and datetime.now() - cached["at"] < FOREIGN_TTL:
        return cached["s"]
    end = today_tw()
    r = requests.get(FINMIND_URL, headers=_HEADERS, timeout=_TIMEOUT, params={
        "dataset": "TaiwanStockTotalInstitutionalInvestors",
        "start_date": (end - timedelta(days=days)).strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d")})
    r.raise_for_status()
    s = parse_finmind_foreign(r.json())
    if s is not None:
        cache_mod.ensure_dir(cache_dir)
        cache_mod.save_obj(cache_dir, key, {"at": datetime.now(), "s": s})
    return s
