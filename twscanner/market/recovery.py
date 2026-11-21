"""
大跌後的「止跌訊號」與「劇本線索」。

止跌訊號（四個，全部是當天就能確認的事實）
  1. 恐慌退燒：VIX ≤ 25
  2. 站回 20 日線：加權指數收盤 > MA20
  3. 半導體不再破底：費半與 NVDA 近 5 日都沒有創 60 日新低
  4. 外資賣壓減輕：近 5 日外資買超，或賣超不到前 20 日平均（每 5 日）的一半

  回測（scripts/strategy_study/recovery_signals.py）的結論：
  成立越多，之後「再跌的幅度」越小；但成立不代表會漲 —— 2000、2008 年都曾全部成立後再跌 30% 以上。
  所以這是降低風險的參考，不是買進訊號；開新倉仍照大盤狀態。

劇本線索（分辨「衝擊型」與「景氣 / 獲利衰退型」大跌）
  - 下跌速度：從一年高點到現在的天數
  - 美國衰退訊號：Sahm 指標（失業率三個月均值比前一年低點高出 0.5 個百分點）
  - 信用利差：Moody's Baa 公司債 − 10 年公債，半年內擴大多少
  - 龍頭獲利：台積電最新月營收年增率
  這些通常比股價慢，不能拿來抓買點；它們翻壞，代表大跌可能從「衝擊」變成「衰退」。

本模組只有純計算；fetch_recovery() 負責抓資料，任何一項抓不到就回 None，不會丟錯。
"""
import logging

import pandas as pd

from twscanner.data import macro
from twscanner.data.revenue import fetch_revenue
from twscanner.market.tw_regime import fetch_twii

log = logging.getLogger(__name__)

VIX_CALM = 25.0
MA_N = 20
LOW_N, LOW_K = 60, 5          # 近 LOW_K 日沒有創 LOW_N 日新低
FLOW_RECENT, FLOW_BASE = 5, 20
DD_APPLY = -0.15              # 距一年高點跌超過 15% 才判斷劇本
FAST_DAYS = 140               # 高點到現在不超過這麼多天 = 跌得快
SAHM_ALERT = 0.5
CREDIT_ALERT = 0.5            # Baa 利差半年擴大（百分點）
CREDIT_LOOKBACK = 126         # 約半年的交易日
REV_SLOW, REV_ALERT = 10.0, 0.0


def _pm(text):
    """數字前的負號統一用 −（與 App 其他地方一致）。"""
    return text.replace("-", "−")


def _clean(s):
    if s is None:
        return None
    s = pd.Series(s).dropna()
    return s if len(s) else None


def no_new_low(s, n=LOW_N, k=LOW_K):
    """近 k 日最低收盤 > 之前 (n−k) 日的最低收盤。資料不足回 None。"""
    s = _clean(s)
    if s is None or len(s) < n:
        return None
    return bool(s.iloc[-k:].min() > s.iloc[-n:-k].min())


def flow_easing(net, recent=FLOW_RECENT, base=FLOW_BASE):
    """外資賣壓減輕：近 recent 日合計 ≥ 0，或賣超小於前 base 日平均（每 recent 日）的一半。回 (ok, 近期, 基準)。"""
    s = _clean(net)
    if s is None or len(s) < recent + base:
        return None, None, None
    now = float(s.iloc[-recent:].sum())
    ref = float(s.iloc[-(recent + base):-recent].sum()) / (base / recent)
    return bool(now >= 0 or (ref < 0 and now > ref * 0.5)), now, ref


def _sig(key, name, ok, value, rule):
    return {"key": key, "name": name, "ok": ok, "value": value, "rule": rule}


def stabilization_signals(tw, vix=None, sox=None, nvda=None, foreign=None):
    """回四個訊號 [{key, name, ok(True/False/None), value(現在的讀數), rule(成立條件)}]。"""
    out = []
    v = _clean(vix)
    if v is None:
        out.append(_sig("vix", "恐慌退燒", None, "VIX 暫無資料", f"VIX ≤ {VIX_CALM:.0f}"))
    else:
        hi = float(v.iloc[-MA_N:].max())
        out.append(_sig("vix", "恐慌退燒", bool(v.iloc[-1] <= VIX_CALM),
                        f"VIX {v.iloc[-1]:.1f}（近 20 日最高 {hi:.1f}）", f"VIX ≤ {VIX_CALM:.0f}"))

    t = _clean(tw)
    if t is None or len(t) < MA_N:
        out.append(_sig("ma20", "站回 20 日線", None, "加權指數暫無資料", "加權指數收盤 > 20 日線"))
    else:
        ma = float(t.iloc[-MA_N:].mean())
        gap = (float(t.iloc[-1]) / ma - 1) * 100
        out.append(_sig("ma20", "站回 20 日線", bool(t.iloc[-1] > ma),
                        _pm(f"收盤 {t.iloc[-1]:,.0f}，20 日線 {ma:,.0f}（{gap:+.1f}%）"), "加權指數收盤 > 20 日線"))

    parts, oks = [], []
    for lab, s in (("費半", sox), ("NVDA", nvda)):
        ok = no_new_low(s)
        s = _clean(s)
        if ok is None:
            parts.append(f"{lab} 暫無資料")
            continue
        oks.append(ok)
        low = float(s.iloc[-LOW_N:].min())
        parts.append(f"{lab} {'未破底' if ok else '近 5 日創新低'}（距 60 日低點 {_pm(f'{(s.iloc[-1] / low - 1) * 100:+.1f}')}%）")
    out.append(_sig("semi", "半導體不再破底", (all(oks) if len(oks) == 2 else None), "；".join(parts),
                    f"費半與 NVDA 近 {LOW_K} 日都沒有創 {LOW_N} 日新低"))

    ok, now, ref = flow_easing(foreign)
    if ok is None:
        out.append(_sig("foreign", "外資賣壓減輕", None, "外資資料暫無", "近 5 日買超，或賣超不到前 20 日平均的一半"))
    else:
        out.append(_sig("foreign", "外資賣壓減輕", ok,
                        _pm(f"近 5 日 {now:+,.0f} 億；前 20 日平均每 5 日 {ref:+,.0f} 億"),
                        "近 5 日買超，或賣超不到前 20 日平均的一半"))
    return out


def _clue(key, name, verdict, value, note):
    """verdict: 'shock'（偏衝擊型）、'recession'（偏衰退型）、'neutral'、None（無資料或不適用）。"""
    return {"key": key, "name": name, "verdict": verdict, "value": value, "note": note}


def drawdown(tw, window=250):
    """回 (距一年高點的跌幅, 高點日期, 高點到最後一天的日曆天數)。"""
    t = _clean(tw)
    if t is None or len(t) < 20:
        return None, None, None
    w = t.iloc[-window:]
    peak_t = w.idxmax()
    return float(t.iloc[-1] / w.max() - 1), peak_t, int((pd.Timestamp(t.index[-1]) - pd.Timestamp(peak_t)).days)


def scenario_clues(tw, sahm=None, baa=None, tsmc_yoy=None):
    out = []
    dd, peak_t, days = drawdown(tw)
    if dd is None:
        out.append(_clue("speed", "下跌速度", None, "暫無資料", ""))
    elif dd > DD_APPLY:
        out.append(_clue("speed", "下跌速度", None, f"距一年高點 {dd * 100:+.1f}%",
                         "跌幅不到 15%，還不用分劇本"))
    else:
        fast = days <= FAST_DAYS
        out.append(_clue("speed", "下跌速度", "shock" if fast else "neutral",
                         f"{pd.Timestamp(peak_t):%Y/%m/%d} 高點以來 {days} 天跌 {abs(dd) * 100:.0f}%",
                         "跌得快：1998、2002、2015、2020 這類急跌都在 25 個月內收復（其中 1998、2002 先再跌 17–26%）" if fast
                         else "跌得慢：2000、2008 的長空頭都屬於這種，但也有慢跌後收復的例子"))

    s = _clean(sahm)
    if s is None:
        out.append(_clue("sahm", "美國衰退訊號", None, "暫無資料", ""))
    else:
        v = float(s.iloc[-1])
        out.append(_clue("sahm", "美國衰退訊號", "recession" if v >= SAHM_ALERT else "shock",
                         f"Sahm 指標 {v:.2f}（{pd.Timestamp(s.index[-1]):%Y/%m}）",
                         "≥ 0.5 代表就業已惡化到衰退門檻；2001、2008 年大跌時都已亮燈"))

    b = _clean(baa)
    if b is None or len(b) <= CREDIT_LOOKBACK:
        out.append(_clue("credit", "信用利差", None, "暫無資料", ""))
    else:
        chg = float(b.iloc[-1] - b.iloc[-1 - CREDIT_LOOKBACK])
        out.append(_clue("credit", "信用利差", "recession" if chg >= CREDIT_ALERT else "shock",
                         _pm(f"Baa 公司債利差 {b.iloc[-1]:.2f}%，半年 {chg:+.2f}"),
                         "半年擴大 0.5 以上代表企業借錢變難；2000、2008 都有，但 2011、2015、2020 也有過"))

    if tsmc_yoy is None:
        out.append(_clue("revenue", "龍頭獲利", None, "台積電營收暫無資料", ""))
    else:
        y = float(tsmc_yoy)
        verdict = "recession" if y < REV_ALERT else ("neutral" if y < REV_SLOW else "shock")
        out.append(_clue("revenue", "龍頭獲利", verdict, _pm(f"台積電最新月營收年增 {y:+.0f}%"),
                         "營收通常比股價晚 3–6 個月反映：2008 年 7 月時還在 +17%，半年後變 −50%"))
    return out


def summarize(signals, clues):
    ok = sum(1 for s in signals if s["ok"])
    known = sum(1 for s in signals if s["ok"] is not None)
    warn = sum(1 for c in clues if c["verdict"] == "recession")
    shock = sum(1 for c in clues if c["verdict"] == "shock")
    if warn >= 2:
        lean = "線索偏向「景氣 / 獲利衰退型」，這種大跌歷史上跌得深、恢復慢"
    elif warn == 1:
        lean = "有一項衰退線索亮燈，要留意是否擴大"
    elif shock >= 2:
        lean = "線索偏向「衝擊型」，但 2000 年初期也沒有衰退訊號，只能當參考"
    else:
        lean = "線索不足，還分不出劇本"
    return {"ok": ok, "known": known, "total": len(signals), "warn": warn, "lean": lean}


def fetch_recovery(cache_dir=".cache", period="1y", tsmc_yoy=None):
    """抓齊資料並計算。回 {signals, clues, summary, asof}；個別資料失敗時對應項目顯示「暫無資料」。"""
    def safe(fn, *a):
        try:
            return fn(*a)
        except Exception as e:   # 任何單一來源失敗都不影響其他項目
            log.warning("回升訊號資料失敗 %s：%s", getattr(fn, "__name__", fn), e)
            return None

    twdf = safe(fetch_twii, period, cache_dir)
    tw = twdf["Close"] if twdf is not None and len(twdf) else None
    vix = safe(macro.fetch_close, "^VIX", cache_dir, period)
    sox = safe(macro.fetch_close, "^SOX", cache_dir, period)
    nvda = safe(macro.fetch_close, "NVDA", cache_dir, period)
    foreign = safe(macro.fetch_foreign_net, cache_dir)
    sahm = safe(macro.fetch_fred, "SAHMREALTIME", cache_dir)
    baa = safe(macro.fetch_fred, "BAA10Y", cache_dir)
    if tsmc_yoy is None:
        rev = safe(fetch_revenue, cache_dir) or {}
        tsmc_yoy = (rev.get("2330") or {}).get("yoy_pct")
    signals = stabilization_signals(tw, vix, sox, nvda, foreign)
    clues = scenario_clues(tw, sahm, baa, tsmc_yoy)
    asof = pd.Timestamp(_clean(tw).index[-1]) if _clean(tw) is not None else None
    return {"signals": signals, "clues": clues, "summary": summarize(signals, clues), "asof": asof}
