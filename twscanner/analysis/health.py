"""
個股健檢（純計算）：把財報與月營收翻成「指標 · 數值 · 白話 · 好壞」。

設計原則：
- 每一項都附一句白話，讓沒讀過財報的人也看得懂這個數字代表什麼。
- 對短線操作，基本面是「避開地雷」用的背景，不是進出場時機；結論會這樣說。
- 產業差異大的指標（毛利率、負債比）不硬判好壞，只在明顯異常時提醒。
"""

GOOD, NEUTRAL, BAD, NA = "good", "neutral", "bad", "na"
_FIN_WORDS = ("金融", "保險", "銀行", "證券")


def _pct(a, b):
    try:
        return a / b * 100 if a is not None and b else None
    except Exception:
        return None


def period_label(fund):
    """115 年 Q3 → 「2026 年前 3 季累計」"""
    try:
        y = int(fund.get("year")) + 1911
        q = int(fund.get("quarter"))
        return f"{y} 年前 {q} 季累計" if q < 4 else f"{y} 年全年"
    except Exception:
        return "最新一期"


def annualized_eps(fund):
    eps, q = fund.get("eps"), fund.get("quarter")
    try:
        q = int(q)
        return eps * 4 / q if eps is not None and 1 <= q <= 4 else None
    except Exception:
        return None


def _item(key, name, value, verdict, plain, lesson):
    return {"key": key, "name": name, "value": value, "verdict": verdict,
            "plain": plain, "lesson": lesson}


def health_report(fund, rev=None, price=None):
    """
    fund: twscanner.data.fundamentals 的單檔 dict（可為 None）
    rev:  twscanner.data.revenue 的單檔 dict（可為 None）
    price: 目前股價（算本益比 / 股價淨值比）
    回 {period, items, counts, summary, red_flags, valuation}
    """
    fund = fund or {}
    if price is not None and price != price:      # NaN
        price = None
    items, flags = [], []
    is_fin = any(w in (fund.get("industry") or "") for w in _FIN_WORDS)

    # 1. 月營收（最即時的營運指標）
    if rev and rev.get("yoy_pct") is not None:
        yoy, mom = rev["yoy_pct"], rev.get("mom_pct")
        month = rev.get("month") or ""
        mlabel = f"{int(month[:-2]) + 1911} 年 {int(month[-2:])} 月" if len(month) >= 4 else "最新一月"
        if yoy >= 10:
            v, plain = GOOD, f"{mlabel}營收比去年同月多 {yoy:.1f}%，生意明顯變好。"
        elif yoy > -10:
            v, plain = NEUTRAL, f"{mlabel}營收和去年同月差不多（{yoy:+.1f}%）。"
        else:
            v, plain = BAD, f"{mlabel}營收比去年同月少 {abs(yoy):.1f}%，生意在變差。"
            flags.append(f"營收年減 {abs(yoy):.0f}%")
        if mom is not None:
            plain += f"跟上個月比 {mom:+.1f}%。"
        if rev.get("note"):
            plain += f"公司說明：「{rev['note']}」"
        items.append(_item("revenue", "月營收年增率", f"{yoy:+.1f}%", v, plain, "revenue"))

    # 2. 毛利率（產品賺不賺錢、有沒有定價能力）
    gm = fund.get("gross_margin")
    if gm is not None:
        if gm >= 40:
            v, plain = GOOD, f"每賣 100 元，扣掉成本還剩 {gm:.0f} 元，產品有定價能力。"
        elif gm >= 10:
            v, plain = NEUTRAL, f"每賣 100 元，扣掉成本剩 {gm:.0f} 元，屬一般水準（各產業差很多）。"
        else:
            v, plain = NEUTRAL, f"每賣 100 元只剩 {gm:.0f} 元，屬薄利型（代工、通路常見），要靠量取勝。"
        items.append(_item("gross_margin", "毛利率", f"{gm:.1f}%", v, plain, "margin"))

    # 3. 本業是否賺錢 + 業外依賴
    op, net = fund.get("op_income_k"), fund.get("net_income_k")
    opm = fund.get("op_margin") if fund.get("op_margin") is not None else _pct(op, fund.get("revenue_k"))
    if opm is not None or op is not None:
        if op is not None and op <= 0 and net is not None and net > 0:
            v = BAD
            plain = "本業在虧錢，帳上的獲利主要來自業外（投資收益、匯兌等），這種獲利比較不穩定。"
            flags.append("本業虧損、靠業外")
        elif opm is not None and opm <= 0:
            v, plain = BAD, "本業在虧錢：營收不夠支付成本和營運費用。"
            flags.append("本業虧損")
        elif opm is not None and opm >= 15:
            v, plain = GOOD, f"本業很會賺錢：每 100 元營收有 {opm:.0f} 元是本業利潤。"
        else:
            v, plain = NEUTRAL, f"本業有賺錢，每 100 元營收約 {opm:.0f} 元是本業利潤。" if opm is not None \
                else "本業有賺錢。"
        if v != BAD and op and net and op > 0 and net / op > 1.5:
            plain += "不過獲利有不小比例來自業外。"
        items.append(_item("op_margin", "營業利益率（本業）",
                           f"{opm:.1f}%" if opm is not None else "—", v, plain, "op_income"))

    # 4. EPS 與本益比
    eps = fund.get("eps")
    eps_y = annualized_eps(fund)
    pe = price / eps_y if (price and eps_y and eps_y > 0) else None
    if eps is not None:
        if eps <= 0:
            v, plain = BAD, f"{period_label(fund)}每股賺 {eps:.2f} 元，目前是虧損。"
            flags.append("虧損中")
        else:
            v, plain = NEUTRAL, (f"{period_label(fund)}每股賺 {eps:.2f} 元，"
                                 f"照這速度一年約 {eps_y:.2f} 元。" if eps_y else
                                 f"{period_label(fund)}每股賺 {eps:.2f} 元。")
        items.append(_item("eps", "每股盈餘 EPS", f"{eps:.2f} 元", v, plain, "eps"))
    if pe is not None:
        if pe < 12:
            v, plain = GOOD, f"用今年的獲利速度，股價約是 {pe:.0f} 年的獲利，偏便宜（也可能是市場預期會衰退）。"
        elif pe <= 25:
            v, plain = NEUTRAL, f"股價約是 {pe:.0f} 年的獲利，屬合理區間。"
        elif pe <= 40:
            v, plain = NEUTRAL, f"股價約是 {pe:.0f} 年的獲利，市場給了高成長期待。"
        else:
            v, plain = BAD, f"股價約是 {pe:.0f} 年的獲利，非常貴，期待落空時跌幅會很大。"
        items.append(_item("pe", "本益比（估）", f"{pe:.1f} 倍", v, plain, "pe"))

    # 5. 財務結構
    assets, liab = fund.get("assets_k"), fund.get("liabilities_k")
    debt = _pct(liab, assets)
    if debt is not None:
        if is_fin:
            v, plain = NA, f"負債比 {debt:.0f}%。金融業用存款與保單經營，負債比本來就高，不適用一般標準。"
        elif debt < 40:
            v, plain = GOOD, f"資產中只有 {debt:.0f}% 是借來的，財務很穩。"
        elif debt <= 60:
            v, plain = NEUTRAL, f"資產中有 {debt:.0f}% 是借來的，屬一般水準。"
        else:
            v, plain = BAD, f"資產中有 {debt:.0f}% 是借來的，景氣不好時壓力較大。"
            flags.append(f"負債比 {debt:.0f}%")
        items.append(_item("debt", "負債比", f"{debt:.0f}%", v, plain, "balance"))
    cur = _pct(fund.get("current_assets_k"), fund.get("current_liabilities_k"))
    if cur is not None and not is_fin:
        if cur >= 150:
            v, plain = GOOD, f"一年內可變現的資產是一年內要還的債的 {cur / 100:.1f} 倍，短期不缺錢。"
        elif cur >= 100:
            v, plain = NEUTRAL, f"一年內可變現的資產剛好夠還短期債（{cur / 100:.1f} 倍）。"
        else:
            v, plain = BAD, f"一年內可變現的資產不夠還短期債（{cur / 100:.1f} 倍），要留意資金調度。"
            flags.append("流動比 < 100%")
        items.append(_item("current", "流動比", f"{cur:.0f}%", v, plain, "balance"))
    bvps = fund.get("bvps")
    pb = price / bvps if (price and bvps and bvps > 0) else None
    if pb is not None:
        items.append(_item("pb", "股價淨值比", f"{pb:.2f} 倍", NEUTRAL,
                           f"股價是每股淨值（{bvps:.1f} 元）的 {pb:.1f} 倍；"
                           + ("市場認為它的獲利能力遠高於帳面資產。" if pb >= 3 else
                              "股價接近帳面價值。" if pb <= 1.2 else "屬一般水準。"),
                           "pb"))

    counts = {k: sum(1 for i in items if i["verdict"] == k) for k in (GOOD, NEUTRAL, BAD)}
    if not items:
        summary = "查無財報資料（上櫃公司、金控或新上市公司目前不支援）。"
    elif flags:
        summary = f"要注意：{'、'.join(flags)}。短線操作也建議避開或縮小部位。"
    elif counts[GOOD] >= 3:
        summary = f"體質良好：{counts[GOOD]} 項良好、沒有明顯地雷。"
    else:
        summary = f"體質普通：{counts[GOOD]} 項良好、{counts[NEUTRAL]} 項普通，沒有明顯地雷。"
    return {"period": period_label(fund) if fund else None, "items": items, "counts": counts,
            "summary": summary, "red_flags": flags,
            "valuation": {"pe": pe, "pb": pb, "eps_annual": eps_y}}
