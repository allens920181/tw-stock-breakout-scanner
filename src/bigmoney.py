# -*- coding: utf-8 -*-
"""
大資金 / 宏觀資金面（只調部位 position_factor，不選股）

三個對台股最直接的「聰明錢」訊號（皆官方/yfinance 免費）：
  1. 外資台指期淨未平倉（期交所）— 外資對「大盤方向」的押注，最早表態、最難騙。
  2. 台幣匯率走勢（USDTWD）— 外資資金進出代理；TWD 升值=流入、貶值=撤離。
  3. 大盤融資水位（TWSE）— 整體散戶槓桿；急增=過熱反指標。

哲學（與 macro.py / market_filter 一致）：宏觀當油門/煞車，不當方向盤。
翻空時全面降碼、提高門檻，而非反手放空個股。
任一資料抓不到 → 該子項中性(50)，永不中斷掃描。
"""
import logging

import requests

from . import cache as cache_mod
from .fetcher import yf  # 重用已設靜音的 yfinance

log = logging.getLogger(__name__)

_TIMEOUT = 25
_HEADERS = {"User-Agent": "Mozilla/5.0 (stock-scan)",
            "Referer": "https://www.taifex.com.tw/cht/3/futContractsDate"}
_TAIFEX_DOWN = "https://www.taifex.com.tw/cht/3/futContractsDateDown"
_TWSE_MARGIN = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"


def _clip(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, float(x)))


# ============ 1. 外資台指期淨未平倉 ============
def parse_foreign_fut_oi(csv_text):
    """
    從期交所 futContractsDateDown CSV 解析『臺股期貨 / 外資』每日多空未平倉淨額(口數)。
    回傳 [(date, net_oi), ...] 依日期排序。純函式（給測試）。
    """
    out = []
    for line in csv_text.splitlines():
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < 14:
            continue
        name, ident = cols[1], cols[2]
        # 商品需為「臺股期貨」本尊（排除小型臺指、電子、金融…）；身份含「外資」
        if name != "臺股期貨" or "外資" not in ident:
            continue
        try:
            net_oi = int(cols[13].replace(",", ""))
        except Exception:
            continue
        out.append((cols[0], net_oi))
    out.sort(key=lambda x: x[0])
    return out


def fetch_foreign_fut_oi(cache_dir, verify=True, use_cache=True):
    """抓近期外資台指期淨未平倉序列，回 {series:[(d,oi)], latest, prev5}。"""
    if use_cache:
        c = cache_mod.load_obj(cache_dir, "foreign_fut_oi")
        if c is not None:
            return c
    out = {"series": [], "latest": None, "prev5": None}
    try:
        # 抓近 ~30 天範圍（一次請求）；日期參數用相對寬鬆字串，期交所自動裁切交易日
        r = requests.post(_TAIFEX_DOWN, headers=_HEADERS, timeout=_TIMEOUT, verify=verify,
                          data={"queryStartDate": "", "queryEndDate": "", "commodityId": ""})
        series = parse_foreign_fut_oi(r.content.decode("big5", "replace"))
        if series:
            out["series"] = series
            out["latest"] = series[-1][1]
            out["prev5"] = series[-6][1] if len(series) >= 6 else series[0][1]
            if use_cache:
                cache_mod.save_obj(cache_dir, "foreign_fut_oi", out)
    except Exception as e:
        log.warning("外資台指期未平倉抓取失敗：%s", e)
    return out


def score_foreign_fut(oi):
    """外資台指期 → 0~100 子分。淨多且增=偏多(高分)，淨空且減=偏空(低分)。"""
    latest, prev5 = oi.get("latest"), oi.get("prev5")
    if latest is None:
        return 50.0, "—"
    # 水位分：以 ±3 萬口為飽和
    level = _clip(50 + latest / 30000 * 50)
    # 動能分：5 日變化，以 ±1 萬口為飽和
    if prev5 is not None:
        chg = latest - prev5
        mom = _clip(50 + chg / 10000 * 50)
    else:
        mom = 50.0
    score = 0.6 * level + 0.4 * mom
    sign = "淨多" if latest > 0 else ("淨空" if latest < 0 else "中性")
    detail = f"外資台指期{sign}{abs(latest):,}口"
    return score, detail


# ============ 2. 台幣匯率（USDTWD） ============
def fetch_twd_trend(period, cache_dir, use_cache=True):
    """USDTWD 近 20 日變化%。回 {twd_chg_pct, last}。USDTWD 下跌=台幣升值=資金流入。"""
    out = {"twd_chg_pct": None, "last": None}
    try:
        df = cache_mod.load_df(cache_dir, "USDTWD", "fx") if use_cache else None
        if df is None or df.empty:
            df = yf.download("TWD=X", period=period, interval="1d",
                            auto_adjust=False, progress=False)
            if df is not None and not df.empty:
                cache_mod.save_df(cache_dir, "USDTWD", "fx", df)
        if df is None or df.empty or len(df) < 21:
            return out
        close = df["Close"]
        if hasattr(close, "columns"):
            close = close.iloc[:, 0]
        last = float(close.iloc[-1])
        past = float(close.iloc[-21])
        out["last"] = last
        out["twd_chg_pct"] = (last - past) / past * 100 if past else None
    except Exception as e:
        log.warning("USDTWD 抓取失敗：%s", e)
    return out


def score_twd(twd):
    """台幣 → 0~100。升值(USDTWD跌)=流入(高分)；貶值=撤離(低分)。±3% 飽和。"""
    chg = twd.get("twd_chg_pct")
    if chg is None:
        return 50.0, "—"
    score = _clip(50 - chg / 3.0 * 50)   # USDTWD 跌 → chg<0 → 高分
    if chg <= -0.5:
        d = f"台幣升{abs(chg):.1f}%(資金流入)"
    elif chg >= 0.5:
        d = f"台幣貶{chg:.1f}%(資金撤離)"
    else:
        d = "台幣持平"
    return score, d


# ============ 3. 大盤融資水位 ============
def fetch_market_margin(cache_dir, dates, verify=True, use_cache=True):
    """
    抓大盤融資餘額(金額,仟元)序列。dates: 由近到遠的 YYYYMMDD 清單（交易日由呼叫端給）。
    回 {series:[(date, bal)], latest, prev}。
    """
    if use_cache:
        c = cache_mod.load_obj(cache_dir, "market_margin")
        if c is not None:
            return c
    series = []
    for d in dates:
        try:
            j = requests.get(_TWSE_MARGIN, headers=_HEADERS, timeout=_TIMEOUT, verify=verify,
                            params={"date": d, "selectType": "MS", "response": "json"}).json()
            if j.get("stat") != "OK":
                continue
            for tb in j.get("tables", []):
                for row in tb.get("data", []):
                    if row and "融資金額" in str(row[0]):
                        bal = float(str(row[-1]).replace(",", ""))  # 今日餘額
                        series.append((d, bal))
                        break
        except Exception:
            continue
    series.sort(key=lambda x: x[0])
    out = {"series": series,
           "latest": series[-1][1] if series else None,
           "prev": series[0][1] if len(series) >= 2 else None}
    if series and use_cache:
        cache_mod.save_obj(cache_dir, "market_margin", out)
    return out


def score_market_margin(mg):
    """大盤融資 → 0~100。急增=散戶過熱(反指標,低分)；持平/降=中性偏高。±5% 飽和。"""
    latest, prev = mg.get("latest"), mg.get("prev")
    if latest is None or prev is None or prev == 0:
        return 50.0, "—"
    chg = (latest - prev) / prev * 100
    score = _clip(50 - chg / 5.0 * 50)   # 融資增 → 低分
    if chg >= 2:
        d = f"大盤融資增{chg:.1f}%(散戶過熱)"
    elif chg <= -2:
        d = f"大盤融資減{abs(chg):.1f}%(去槓桿)"
    else:
        d = "融資持平"
    return score, d


# ============ 合成 ============
def combine_bigmoney(fut_score, twd_score, mg_score, weights=None):
    """三子分加權 → 綜合分 + position_factor(0.4~1.0，只降不增；宏觀是煞車不是油門)。"""
    w = weights or {"fut": 0.5, "twd": 0.3, "margin": 0.2}
    score = (w["fut"] * fut_score + w["twd"] * twd_score + w["margin"] * mg_score)
    if score >= 60:
        factor = 1.0
    elif score >= 45:
        factor = 0.75
    else:
        factor = 0.5
    return round(score, 1), factor


def classify_bigmoney(cache_dir=".cache", period="6mo", verify=True,
                      margin_dates=None, weights=None):
    """
    主入口：抓三指標 → 子分 → 合成。回傳含 label/detail/position_factor 的 state。
    margin_dates: 近數個交易日 YYYYMMDD（由 runner 用 TWSE 交易日給）；None 則略過融資子項。
    """
    oi = fetch_foreign_fut_oi(cache_dir, verify=verify)
    twd = fetch_twd_trend(period, cache_dir)
    mg = fetch_market_margin(cache_dir, margin_dates or [], verify=verify) if margin_dates else {"latest": None, "prev": None}

    fs, fd = score_foreign_fut(oi)
    ts, td = score_twd(twd)
    ms, md = score_market_margin(mg)
    score, factor = combine_bigmoney(fs, ts, ms, weights)

    if factor >= 1.0:
        label = "🟢 資金偏多"
    elif factor >= 0.75:
        label = "🟡 資金中性"
    else:
        label = "🔴 資金偏空"
    detail = " · ".join([d for d in (fd, td, md) if d and d != "—"]) or "資金面資料不足"
    return {
        "label": label, "detail": detail, "score": score,
        "position_factor": factor,
        "foreign_fut_oi": oi.get("latest"),
        "foreign_fut_prev5": oi.get("prev5"),
        "twd_chg_pct": twd.get("twd_chg_pct"),
        "margin_chg_pct": (
            (mg["latest"] - mg["prev"]) / mg["prev"] * 100
            if mg.get("latest") and mg.get("prev") else None),
        "subscores": {"fut": round(fs, 0), "twd": round(ts, 0), "margin": round(ms, 0)},
    }
