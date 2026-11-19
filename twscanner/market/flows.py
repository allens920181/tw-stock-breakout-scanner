# -*- coding: utf-8 -*-
"""
資金流向觀測（台股 + 美股 + 台美連動）—— 只做「觀測/視覺化」，不影響選股與部位。

真正的「基金申贖金流」(ETF fund flows) 沒有免費可靠來源，這裡用可公開取得、
且業界常用的代理指標，回答「錢現在往哪裡去」：

美股（yfinance，免費）
  - 類股輪動 RRG：各類股 ETF 對 SPY 的相對強弱(RS-Ratio) × 相對強弱動能(RS-Momentum)
    四象限：領先(資金流入中) / 轉弱(開始流出) / 落後(流出) / 改善(開始流入)
  - Chaikin Money Flow (CMF20)：收盤在當日區間的位置 × 成交量 → 買盤/賣盤主導
  - 成交金額放大倍數：近 5 日均成交金額 ÷ 近 60 日均 → 資金是否「湧入」
  - 風險偏好比值：攻擊/防禦(XLY÷XLP)、高收益債/公債(HYG÷IEF)、小型/大型、半導體/大盤
台股（TWSE 官方，免費免 key）
  - 三大法人每日買賣金額（BFI82U）
  - 類股成交比重變化（BFIAMU）：今天成交金額佔比 vs 近 20 日平均 → 錢往哪個類股集中
  - 外資/投信 依產業買賣超（T86 股數 × 最新收盤價，估算金額）
台美連動
  - 台股隔日報酬 vs 前一晚 S&P500 / 費半 的相關係數、同向率、Beta
  - 台積電 ADR 溢價（TSM ÷ (2330×5÷USDTWD) − 1）：美國投資人對台灣科技股的追價熱度

任何資料抓不到 → 該區塊回空，UI 端顯示「暫無資料」，永不拋錯中斷 App。
"""
import json
import logging
import os
import time
from datetime import timedelta

import numpy as np
import pandas as pd
import requests

from twscanner.core import cache as cache_mod
from twscanner.core.tz import today_tw
from twscanner.data.prices import yf  # 重用已設靜音的 yfinance
from twscanner.data.sectors import fetch_sectors

log = logging.getLogger(__name__)

_TIMEOUT = 20
_HEADERS = {"User-Agent": "Mozilla/5.0 (stock-scan)"}
_SLEEP = 0.8   # TWSE 請求間隔（太密會被暫時限流，回空白內容）

# ---------------------------------------------------------------
# 標的定義
# ---------------------------------------------------------------
US_BENCH = "SPY"

US_SECTORS = {
    "XLK": "科技", "SMH": "半導體", "XLC": "通訊服務", "XLY": "非必需消費",
    "XLF": "金融", "XLI": "工業", "XLV": "醫療保健", "XLP": "必需消費",
    "XLE": "能源", "XLB": "原物料", "XLU": "公用事業", "XLRE": "房地產",
}

CROSS_ASSETS = {
    "SPY": "美股大盤", "QQQ": "那斯達克100", "IWM": "美國小型股",
    "TLT": "美國長天期公債", "HYG": "高收益債", "GLD": "黃金",
    "UUP": "美元", "EEM": "新興市場", "EWT": "台灣 ETF", "BTC-USD": "比特幣",
}

RISK_RATIOS = [
    ("XLY", "XLP", "攻擊 / 防禦", "非必需消費 ÷ 必需消費：上升=敢花錢、追成長"),
    ("HYG", "IEF", "信用風險偏好", "高收益債 ÷ 中期公債：上升=願意承擔風險"),
    ("IWM", "SPY", "小型 / 大型", "小型股 ÷ 大盤：上升=資金擴散、行情健康"),
    ("SMH", "SPY", "半導體 / 大盤", "半導體 ÷ 大盤：上升=科技/AI 資金集中，台股最受惠"),
]

LINK_SYMBOLS = ["^TWII", "^GSPC", "^SOX", "TSM", "2330.TW", "TWD=X"]

QUADRANT = {
    "leading": ("領先", "資金流入中"),
    "weakening": ("轉弱", "資金開始流出"),
    "lagging": ("落後", "資金流出"),
    "improving": ("改善", "資金開始流入"),
}

# BFIAMU 中的「母類別」會與子類別重複計算 → 排除
_TW_PARENT_SECTORS = {"電子類", "化學生技醫療類"}


def _to_float(x):
    try:
        s = str(x).replace(",", "").strip()
        return float(s) if s not in ("", "--", "-") else None
    except Exception:
        return None


# ===============================================================
# 純計算（給測試）
# ===============================================================
def cmf(high, low, close, volume, n=20):
    """Chaikin Money Flow：Σ(MFM×Vol)/ΣVol，MFM=((C-L)-(H-C))/(H-L)。範圍 -1~+1。"""
    rng = (high - low).replace(0, np.nan)
    mfm = ((close - low) - (high - close)) / rng
    mfv = (mfm.fillna(0) * volume)
    return mfv.rolling(n).sum() / volume.rolling(n).sum()


def rrg(close, bench, ratio_n=20, mom_n=5, smooth=5):
    """
    簡化版 RRG（Relative Rotation Graph）。
      RS        = EMA(close / bench, smooth)            先平滑，避免單日雜訊讓軌跡亂跳
      RS-Ratio  = 100 × RS / SMA(RS, ratio_n)           >100 = 相對大盤強
      RS-Mom    = EMA(100 × RS-Ratio / RS-Ratio.shift(mom_n), smooth)   >100 = 相對強度在變強
    回 DataFrame[ratio, mom]（index 同 close）。
    """
    rs = (close / bench).ewm(span=smooth, adjust=False).mean()
    ratio = 100 * rs / rs.rolling(ratio_n).mean()
    mom = (100 * ratio / ratio.shift(mom_n)).ewm(span=smooth, adjust=False).mean()
    return pd.DataFrame({"ratio": ratio, "mom": mom})


def quadrant(ratio, mom):
    if ratio is None or mom is None or pd.isna(ratio) or pd.isna(mom):
        return None
    if ratio >= 100:
        return "leading" if mom >= 100 else "weakening"
    return "improving" if mom >= 100 else "lagging"


def pct_change_n(s, n):
    s = s.dropna()
    if len(s) <= n:
        return None
    return float(s.iloc[-1] / s.iloc[-1 - n] - 1) * 100


def sector_share_shift(values, lookback=20):
    """
    values: DataFrame index=日期(升冪) columns=類股 值=成交金額。
    回 DataFrame[今日比重%, 平均比重%, 比重變化pp, 今日金額億]，依變化降冪。
    """
    if values is None or values.empty:
        return pd.DataFrame()
    share = values.div(values.sum(axis=1), axis=0) * 100
    today = share.iloc[-1]
    base = share.iloc[-(lookback + 1):-1].mean() if len(share) > 1 else today
    out = pd.DataFrame({
        "今日比重%": today.round(2),
        "平均比重%": base.round(2),
        "比重變化pp": (today - base).round(2),
        "今日金額億": (values.iloc[-1] / 1e8).round(1),
    })
    return out.sort_values("比重變化pp", ascending=False)


def _naive_ns(idx):
    idx = pd.to_datetime(idx)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return idx.astype("datetime64[ns]")


def lead_lag(tw_close, us_close, window=120):
    """
    台股「隔日」報酬 vs 美股「前一晚」報酬。
    美股在台灣時間清晨收盤 → 台股日期 d 對應「日期 < d 的最近一個美股交易日」。
    回 {corr, same_dir, beta, n, df}；df 為散佈圖資料（us_ret, tw_ret）。
    """
    tw = tw_close.dropna().pct_change().dropna() * 100
    us = us_close.dropna().pct_change().dropna() * 100
    if tw.empty or us.empty:
        return {"corr": None, "same_dir": None, "beta": None, "n": 0, "df": pd.DataFrame()}
    tw.index = _naive_ns(tw.index)
    us.index = _naive_ns(us.index)
    us_prev = us.copy()
    us_prev.index = us_prev.index + pd.Timedelta(days=1)   # 美股 d 的報酬 → 台股 ≥ d+1 可用
    us_prev = us_prev.sort_index()
    aligned = pd.merge_asof(
        tw.rename("tw_ret").to_frame().sort_index(),
        us_prev.rename("us_ret").to_frame(),
        left_index=True, right_index=True, direction="backward",
        tolerance=pd.Timedelta(days=4),
    ).dropna().tail(window)
    n = len(aligned)
    if n < 20:
        return {"corr": None, "same_dir": None, "beta": None, "n": n, "df": aligned}
    corr = float(aligned["tw_ret"].corr(aligned["us_ret"]))
    same = float((np.sign(aligned["tw_ret"]) == np.sign(aligned["us_ret"])).mean() * 100)
    var = float(aligned["us_ret"].var())
    beta = float(aligned["tw_ret"].cov(aligned["us_ret"]) / var) if var else None
    return {"corr": corr, "same_dir": same, "beta": beta, "n": n, "df": aligned}


def adr_premium(tsm, tw2330, usdtwd, ratio=5):
    """台積電 ADR 溢價%。1 ADR = 5 股普通股。"""
    df = pd.concat([tsm.rename("tsm"), tw2330.rename("tw"), usdtwd.rename("fx")], axis=1)
    df.index = _naive_ns(df.index)
    df = df.sort_index().ffill().dropna()
    if df.empty:
        return pd.Series(dtype=float)
    return ((df["tsm"] / (df["tw"] * ratio / df["fx"]) - 1) * 100).rename("ADR溢價%")


# ===============================================================
# 美股 / 跨市場價格
# ===============================================================
def _all_us_symbols():
    syms = set(US_SECTORS) | set(CROSS_ASSETS) | {US_BENCH} | set(LINK_SYMBOLS)
    for a, b, _, _ in RISK_RATIOS:
        syms.update([a, b])
    return sorted(syms)


def fetch_prices(cache_dir=".cache", period="1y", use_cache=True, retries=2):
    """一次批次下載所有標的 → {Close, High, Low, Volume} 各一個 DataFrame。當日快取。"""
    if use_cache:
        c = cache_mod.load_obj(cache_dir, "flows_prices")
        if c is not None:
            return c
    syms = _all_us_symbols()
    data = None
    for i in range(retries + 1):
        try:
            data = yf.download(syms, period=period, interval="1d",
                               auto_adjust=True, progress=False, threads=True)
        except Exception as e:
            log.warning("資金流向 yfinance 下載失敗：%s", e)
            data = None
        if data is not None and not data.empty:
            missing = [s for s in syms if s not in data["Close"].columns
                       or data["Close"][s].dropna().empty]
            if not missing or i == retries:
                break
            time.sleep(2 + i * 2)
        else:
            time.sleep(2 + i * 2)
    if data is None or data.empty:
        return {}
    out = {}
    for f in ("Close", "High", "Low", "Volume"):
        try:
            df = data[f].copy()
            df.index = _naive_ns(df.index)
            out[f] = df
        except Exception:
            out[f] = pd.DataFrame()
    # 有缺漏時不快取完整版，讓下次再補抓
    complete = all(s in out["Close"].columns and out["Close"][s].notna().sum() > 60 for s in syms)
    if use_cache and complete:
        cache_mod.ensure_dir(cache_dir)
        cache_mod.save_obj(cache_dir, "flows_prices", out)
    return out


def _col(px, field, sym):
    df = px.get(field)
    if df is None or df.empty or sym not in df.columns:
        return pd.Series(dtype=float)
    return df[sym].dropna()


def flow_table(px, symbols, bench=US_BENCH):
    """各標的資金指標表。symbols: {代號: 中文名}。"""
    rows = []
    bclose = _col(px, "Close", bench)
    for sym, name in symbols.items():
        c = _col(px, "Close", sym)
        if len(c) < 65:
            continue
        h, lo, v = _col(px, "High", sym), _col(px, "Low", sym), _col(px, "Volume", sym)
        row = {"代號": sym, "名稱": name,
               "5日%": pct_change_n(c, 5), "20日%": pct_change_n(c, 20),
               "60日%": pct_change_n(c, 60)}
        if not bclose.empty and sym != bench:
            b20 = pct_change_n(bclose, 20)
            row["相對大盤20日pp"] = (row["20日%"] - b20) if (row["20日%"] is not None and b20 is not None) else None
        else:
            row["相對大盤20日pp"] = 0.0 if sym == bench else None
        # CMF / 成交金額放大（指數、加密貨幣成交量意義不同 → 仍計算，僅供參考）
        if len(v) >= 60 and v.sum() > 0:
            idx = c.index.intersection(h.index).intersection(lo.index).intersection(v.index)
            cm = cmf(h[idx], lo[idx], c[idx], v[idx]).dropna()
            row["CMF20"] = float(cm.iloc[-1]) if not cm.empty else None
            dv = (c[idx] * v[idx])
            base = dv.tail(60).mean()
            row["成交額放大"] = float(dv.tail(5).mean() / base) if base else None
        else:
            row["CMF20"], row["成交額放大"] = None, None
        if sym != bench and not bclose.empty:
            r = rrg(c, bclose.reindex(c.index).ffill()).dropna()
            if not r.empty:
                row["RS_Ratio"], row["RS_Mom"] = float(r["ratio"].iloc[-1]), float(r["mom"].iloc[-1])
                row["象限"] = quadrant(row["RS_Ratio"], row["RS_Mom"])
        rows.append(row)
    df = pd.DataFrame(rows)
    if not df.empty:
        df["資金訊號"] = df.apply(_flow_signal, axis=1)
    return df


def _flow_signal(row):
    """綜合 CMF + 成交額放大 + 象限 → 一句話。"""
    q = row.get("象限")
    cm = row.get("CMF20")
    vol = row.get("成交額放大")
    inflow = (cm is not None and not pd.isna(cm) and cm > 0.05)
    outflow = (cm is not None and not pd.isna(cm) and cm < -0.05)
    hot = (vol is not None and not pd.isna(vol) and vol >= 1.3)
    if q in ("leading", "improving") and inflow:
        s = "🟢 流入"
    elif q in ("lagging", "weakening") and outflow:
        s = "🔴 流出"
    elif inflow:
        s = "🟡 偏流入"
    elif outflow:
        s = "🟠 偏流出"
    else:
        s = "⚪ 中性"
    return s + ("（爆量）" if hot else "")


def rrg_tails(px, symbols, bench=US_BENCH, tail=5, step=2):
    """RRG 散佈圖資料：每檔最近 tail 個點（每 step 日一點）。回 {sym: DataFrame[ratio, mom]}。"""
    bclose = _col(px, "Close", bench)
    out = {}
    if bclose.empty:
        return out
    for sym in symbols:
        c = _col(px, "Close", sym)
        if len(c) < 40:
            continue
        r = rrg(c, bclose.reindex(c.index).ffill()).dropna()
        if r.empty:
            continue
        out[sym] = r.iloc[::-1].iloc[::step].iloc[:tail].iloc[::-1]
    return out


def risk_ratio_series(px, days=120):
    """風險偏好比值（以期初=100 指數化）+ 20 日變化 / 是否站上 50 日均線。"""
    series, stats = {}, []
    for a, b, name, desc in RISK_RATIOS:
        ca, cb = _col(px, "Close", a), _col(px, "Close", b)
        if ca.empty or cb.empty:
            continue
        r = (ca / cb.reindex(ca.index).ffill()).dropna()
        if len(r) < 60:
            continue
        ma50 = r.rolling(50).mean()
        rr = r.tail(days)
        series[name] = rr / rr.iloc[0] * 100
        stats.append({
            "指標": name, "說明": desc,
            "20日變化%": pct_change_n(r, 20),
            "站上50日線": bool(r.iloc[-1] > ma50.iloc[-1]),
        })
    return series, pd.DataFrame(stats)


def risk_appetite_label(stats):
    """依風險偏好比值 → risk-on / risk-off 判斷。"""
    if stats is None or stats.empty:
        return "未知", 0, 0
    up = int(((stats["20日變化%"].fillna(0) > 0) & stats["站上50日線"]).sum())
    down = int(((stats["20日變化%"].fillna(0) < 0) & ~stats["站上50日線"]).sum())
    if up >= 3:
        lab = "🟢 Risk-on（資金追逐風險資產）"
    elif down >= 3:
        lab = "🔴 Risk-off（資金躲進防禦/避險）"
    elif up > down:
        lab = "🟡 偏 Risk-on"
    elif down > up:
        lab = "🟠 偏 Risk-off"
    else:
        lab = "⚪ 方向不明"
    return lab, up, down


def tw_us_linkage(px, window=120):
    tw = _col(px, "Close", "^TWII")
    res = {
        "spx": lead_lag(tw, _col(px, "Close", "^GSPC"), window),
        "sox": lead_lag(tw, _col(px, "Close", "^SOX"), window),
        "adr": adr_premium(_col(px, "Close", "TSM"), _col(px, "Close", "2330.TW"),
                           _col(px, "Close", "TWD=X")),
    }
    return res


# ===============================================================
# 台股（TWSE 官方）— 以「日期」永久快取（歷史資料不會變）
# ===============================================================
def _hist_path(cache_dir):
    return os.path.join(cache_dir, "flows_twse_hist.json")


def _hist_load(cache_dir):
    try:
        with open(_hist_path(cache_dir), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _hist_save(cache_dir, h):
    try:
        cache_mod.ensure_dir(cache_dir)
        # 只保留最近 ~200 筆，避免檔案無限長大
        keys = sorted(h.keys())[-200:]
        with open(_hist_path(cache_dir), "w", encoding="utf-8") as f:
            json.dump({k: h[k] for k in keys}, f, ensure_ascii=False)
    except Exception as e:
        log.warning("資金流向快取寫入失敗：%s", e)


def parse_bfi82u(js):
    """三大法人買賣金額 → {外資, 投信, 自營商}（買賣差額，元）。非交易日回 None。"""
    if not js or js.get("stat") != "OK" or not js.get("data"):
        return None
    out = {"外資": 0.0, "投信": 0.0, "自營商": 0.0}
    for row in js["data"]:
        name, net = str(row[0]), _to_float(row[-1]) or 0.0
        if name.startswith("合計"):
            continue
        if "外資" in name:
            out["外資"] += net
        elif "投信" in name:
            out["投信"] += net
        elif "自營商" in name:
            out["自營商"] += net
    return out


def parse_bfiamu(js):
    """各類指數成交值 → {類股: 成交金額(元)}（排除母類別）。"""
    if not js or js.get("stat") != "OK" or not js.get("data"):
        return None
    out = {}
    for row in js["data"]:
        name = str(row[0]).strip().replace("指數", "")
        if name in _TW_PARENT_SECTORS:
            continue
        val = _to_float(row[2])
        if val is not None:
            out[name.removesuffix("類")] = val
    return out or None


def parse_t86(js):
    """T86 → {code: [外資淨股數, 投信淨股數]}。"""
    if not js or js.get("stat") != "OK" or not js.get("data"):
        return None
    fields = js.get("fields") or []

    def idx(key, default):
        for i, f in enumerate(fields):
            if key in f:
                return i
        return default
    i_f = idx("外陸資買賣超股數(不含外資自營商)", 4)
    i_t = idx("投信買賣超股數", 10)
    out = {}
    for row in js["data"]:
        code = str(row[0]).strip()
        if not code or not code[0].isdigit():
            continue
        out[code] = [_to_float(row[i_f]) or 0.0, _to_float(row[i_t]) or 0.0]
    return out or None


def _get_json(url, params, verify=True, retries=2):
    """
    回 (json, ok)。ok=False 代表網路錯誤/被限流（之後應重試，不可快取成『休市』）；
    ok=True 且 json.stat != 'OK' 代表 TWSE 明確回覆無資料（休市或尚未公布）。
    """
    for i in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT, verify=verify)
            return r.json(), True
        except Exception as e:
            if i == retries:
                log.warning("TWSE %s %s 失敗：%s", url.rsplit("/", 1)[-1],
                            params.get("date") or params.get("dayDate"), e)
            else:
                time.sleep(3 * (i + 1))   # 被限流時退避
    return None, False


def fetch_tw_flows(cache_dir=".cache", days=20, inst_sector_days=5, verify=True,
                   progress_cb=None):
    """
    往回找 `days` 個交易日，抓 三大法人金額 + 類股成交值；最近 inst_sector_days 日另抓 T86。
    回 {inst: DataFrame(億), sector_values: DataFrame(元), t86: [{code:[f,t]}…], dates:[…]}
    """
    hist = _hist_load(cache_dir)
    dirty = False
    inst_rows, sec_rows, t86_list, dates = [], [], [], []
    off, max_off = 0, days * 2 + 10
    today = today_tw()
    while len(dates) < days and off < max_off:
        day = today - timedelta(days=off)
        off += 1
        if day.weekday() >= 5:      # 週末直接略過，不打 API
            continue
        d = day.strftime("%Y%m%d")
        rec = hist.get(d)
        if rec is None or (not rec.get("closed") and rec.get("sector") is None):
            if progress_cb:
                progress_cb(len(dates), days, d)
            rec = dict(rec or {})
            if "inst" not in rec:
                js, ok = _get_json("https://www.twse.com.tw/rwd/zh/fund/BFI82U",
                                   {"type": "day", "dayDate": d, "response": "json"}, verify)
                time.sleep(_SLEEP)
                if not ok:
                    continue                      # 網路/限流：本次略過，下次重試
                inst = parse_bfi82u(js)
                if inst is None:
                    # TWSE 明確回覆無資料；今天可能只是尚未公布 → 不快取
                    if d != today.strftime("%Y%m%d"):
                        hist[d] = {"closed": True}
                        dirty = True
                    continue
                rec["inst"] = inst
            js, ok = _get_json("https://www.twse.com.tw/rwd/zh/afterTrading/BFIAMU",
                               {"date": d, "response": "json"}, verify)
            time.sleep(_SLEEP)
            rec["sector"] = (parse_bfiamu(js) or {}) if ok else None   # None → 下次補抓
            hist[d] = rec
            dirty = True
        if rec.get("closed"):
            continue
        dates.append(d)
        inst_rows.append({"日期": d, **{k: v / 1e8 for k, v in rec["inst"].items()}})
        if rec.get("sector"):
            sec_rows.append({"日期": d, **rec["sector"]})
        if len(dates) <= inst_sector_days:
            t86 = rec.get("t86")
            if t86 is None:
                js, _ok = _get_json("https://www.twse.com.tw/rwd/zh/fund/T86",
                                    {"date": d, "selectType": "ALLBUT0999", "response": "json"},
                                    verify)
                t86 = parse_t86(js)
                time.sleep(_SLEEP)
                if t86:
                    rec["t86"] = t86
                    dirty = True
            if t86:
                t86_list.append(t86)
    # T86 只需要最近幾天：較舊的日子清掉以縮小快取
    for d in list(hist.keys()):
        if d not in dates[:inst_sector_days] and isinstance(hist[d], dict) and "t86" in hist[d]:
            hist[d].pop("t86", None)
            dirty = True
    if dirty:
        _hist_save(cache_dir, hist)

    inst = pd.DataFrame(inst_rows)
    if not inst.empty:
        inst["日期"] = pd.to_datetime(inst["日期"])
        inst = inst.set_index("日期").sort_index()
    secv = pd.DataFrame(sec_rows)
    if not secv.empty:
        secv["日期"] = pd.to_datetime(secv["日期"])
        secv = secv.set_index("日期").sort_index().fillna(0)
    return {"inst": inst, "sector_values": secv, "t86": t86_list, "dates": dates}


def fetch_latest_close(cache_dir=".cache", verify=True, use_cache=True):
    """TWSE OpenAPI STOCK_DAY_ALL → {code: 收盤價}（最新交易日）。"""
    if use_cache:
        c = cache_mod.load_obj(cache_dir, "flows_close_all")
        if c is not None:
            return c
    out = {}
    try:
        data = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
                            headers=_HEADERS, timeout=_TIMEOUT, verify=verify).json()
        for row in data:
            p = _to_float(row.get("ClosingPrice"))
            if p:
                out[str(row.get("Code", "")).strip()] = p
    except Exception as e:
        log.warning("STOCK_DAY_ALL 失敗：%s", e)
    if out and use_cache:
        cache_mod.ensure_dir(cache_dir)
        cache_mod.save_obj(cache_dir, "flows_close_all", out)
    return out


def sector_inst_flow(t86_list, sectors_map, close_map):
    """
    外資/投信 依產業累計買賣超（億元，估算 = 淨股數 × 最新收盤）。
    回 DataFrame index=產業 columns=[外資, 投信, 合計]，依合計降冪。
    """
    if not t86_list or not sectors_map or not close_map:
        return pd.DataFrame()
    agg = {}
    for day in t86_list:
        for code, (f_sh, t_sh) in day.items():
            ind, px = sectors_map.get(code), close_map.get(code)
            if not ind or not px:
                continue
            a = agg.setdefault(ind, [0.0, 0.0])
            a[0] += f_sh * px / 1e8
            a[1] += t_sh * px / 1e8
    if not agg:
        return pd.DataFrame()
    df = pd.DataFrame.from_dict(agg, orient="index", columns=["外資", "投信"]).round(1)
    df["合計"] = (df["外資"] + df["投信"]).round(1)
    return df.sort_values("合計", ascending=False)


def fetch_tw_sector_inst(tw, cache_dir=".cache", verify=True):
    sectors_map = fetch_sectors(cache_dir, verify=verify)
    close_map = fetch_latest_close(cache_dir, verify=verify)
    return sector_inst_flow(tw.get("t86") or [], sectors_map, close_map)


# ===============================================================
# 摘要：把所有指標濃縮成「錢現在往哪去」
# ===============================================================
def build_summary(us_sec=None, us_cross=None, risk_stats=None, tw=None,
                  tw_share=None, tw_inst_sec=None, link=None):
    """回 {us: [str], tw: [str], link: [str]}，每條為一句可讀結論。"""
    us_lines, tw_lines, link_lines = [], [], []

    # ---- 美國 ----
    if risk_stats is not None and not risk_stats.empty:
        lab, up, down = risk_appetite_label(risk_stats)
        us_lines.append(f"風險胃口：**{lab}**（4 項風險比值中 {up} 項向上、{down} 項向下）")
    if us_sec is not None and not us_sec.empty and "象限" in us_sec:
        def names(qs):
            d = us_sec[us_sec["象限"].isin(qs)].sort_values("RS_Mom", ascending=False)
            return "、".join(d["名稱"].head(4)) or "—"
        us_lines.append(f"美股類股資金流入：**{names(['leading'])}**；剛開始流入：{names(['improving'])}")
        us_lines.append(f"美股類股資金流出：**{names(['lagging'])}**；開始轉弱：{names(['weakening'])}")
    if us_cross is not None and not us_cross.empty:
        d = us_cross.dropna(subset=["20日%"]).sort_values("20日%", ascending=False)
        if not d.empty:
            top = "、".join(f"{r['名稱']}({r['20日%']:+.1f}%)" for _, r in d.head(3).iterrows())
            bot = "、".join(f"{r['名稱']}({r['20日%']:+.1f}%)" for _, r in d.tail(2).iterrows())
            us_lines.append(f"跨資產近 20 日：最強 {top}；最弱 {bot}")

    # ---- 台灣 ----
    inst = (tw or {}).get("inst")
    if inst is not None and not inst.empty:
        last = inst.iloc[-1]
        s5 = inst.tail(5).sum()
        tw_lines.append(
            f"最新一日（{inst.index[-1]:%m/%d}）外資 **{last['外資']:+.0f} 億**、投信 {last['投信']:+.0f} 億、"
            f"自營商 {last['自營商']:+.0f} 億")
        tw_lines.append(
            f"近 5 日累計：外資 **{s5['外資']:+.0f} 億**、投信 **{s5['投信']:+.0f} 億**、自營商 {s5['自營商']:+.0f} 億")
        f_streak = _streak(inst["外資"])
        if abs(f_streak) >= 3:
            tw_lines.append(f"外資已連續 {abs(f_streak)} 日{'買超' if f_streak > 0 else '賣超'}")
    if tw_share is not None and not tw_share.empty:
        top = tw_share.head(3)
        bot = tw_share.tail(3).iloc[::-1]
        tw_lines.append("成交比重增加（錢湧入）：**" + "、".join(
            f"{i}({r['比重變化pp']:+.1f}pp)" for i, r in top.iterrows()) + "**")
        tw_lines.append("成交比重減少（錢撤出）：" + "、".join(
            f"{i}({r['比重變化pp']:+.1f}pp)" for i, r in bot.iterrows()))
    if tw_inst_sec is not None and not tw_inst_sec.empty:
        buy = tw_inst_sec[tw_inst_sec["合計"] > 0].head(3)
        sell = tw_inst_sec[tw_inst_sec["合計"] < 0].tail(3).iloc[::-1]
        if not buy.empty:
            tw_lines.append("法人加碼族群：**" + "、".join(
                f"{i}({r['合計']:+.0f}億)" for i, r in buy.iterrows()) + "**")
        if not sell.empty:
            tw_lines.append("法人減碼族群：" + "、".join(
                f"{i}({r['合計']:+.0f}億)" for i, r in sell.iterrows()))

    # ---- 連動 ----
    if link:
        for key, nm in (("sox", "費城半導體"), ("spx", "S&P 500")):
            r = link.get(key) or {}
            if r.get("corr") is not None:
                link_lines.append(
                    f"台股隔日 vs 前一晚{nm}：相關係數 **{r['corr']:.2f}**、同向率 {r['same_dir']:.0f}%、"
                    f"Beta {r['beta']:.2f}（近 {r['n']} 日）— {_corr_word(r['corr'])}")
        adr = link.get("adr")
        if adr is not None and len(adr) > 20:
            now, avg = float(adr.tail(5).mean()), float(adr.tail(60).mean())   # 5 日均：降低時差雜訊
            hint = "美國投資人追價台積電，偏多" if now > avg + 2 else (
                "美國投資人熱度降溫" if now < avg - 2 else "熱度與平常相當")
            link_lines.append(f"台積電 ADR 溢價 5 日均 **{now:+.1f}%**（近 60 日平均 {avg:+.1f}%）— {hint}")
    return {"us": us_lines, "tw": tw_lines, "link": link_lines}


def _streak(s):
    """最新值往回同號連續天數；正=連買、負=連賣。"""
    s = s.dropna()
    if s.empty:
        return 0
    sign = np.sign(s.iloc[-1])
    n = 0
    for v in s.iloc[::-1]:
        if np.sign(v) == sign and sign != 0:
            n += 1
        else:
            break
    return int(n * sign)


def _corr_word(c):
    if c >= 0.6:
        return "高度連動，美股夜盤方向很有參考價值"
    if c >= 0.4:
        return "中度連動，美股是重要參考但非絕對"
    if c >= 0.2:
        return "低度連動，台股自身因素影響更大"
    return "幾乎不連動"
