"""部位管理：固定風險法"""
import math


def calc_position(entry, stop, total_capital, risk_pct, position_factor=1.0,
                  lot_size=1000, max_position_pct=0.20,
                  adv_shares=None, max_adv_pct=None):
    """
    回傳 dict:
      risk_per_share
      max_risk_amount
      raw_shares       原始建議股數
      suggested_shares 取整 (1 lot = 1000 股)
      suggested_lots   張數
      cost             進場成本
      cost_pct         佔總資金比例
      warning          風險提示
    """
    if entry <= 0 or stop >= entry:
        return {
            "risk_per_share": None,
            "max_risk_amount": None,
            "raw_shares": 0,
            "suggested_shares": 0,
            "suggested_lots": 0,
            "cost": 0,
            "cost_pct": 0,
            "warning": "停損價無效",
        }

    risk_per_share = entry - stop
    max_risk_amount = total_capital * risk_pct * position_factor

    raw_shares = max_risk_amount / risk_per_share
    suggested_shares = math.floor(raw_shares / lot_size) * lot_size
    suggested_lots = suggested_shares // lot_size

    cost = suggested_shares * entry
    cost_pct = cost / total_capital if total_capital > 0 else 0

    # 單檔最大部位限制
    warning = ""
    if cost_pct > max_position_pct:
        max_cost = total_capital * max_position_pct
        suggested_shares = math.floor(max_cost / entry / lot_size) * lot_size
        suggested_lots = suggested_shares // lot_size
        cost = suggested_shares * entry
        cost_pct = cost / total_capital
        warning = f"已限縮至 {max_position_pct*100:.0f}% 單檔上限"

    # 流動性上限：部位不超過 max_adv_pct × 20日均量（避免進得去出不來）
    if adv_shares and adv_shares > 0 and max_adv_pct and suggested_shares > 0:
        liq_cap_shares = math.floor(adv_shares * max_adv_pct / lot_size) * lot_size
        if liq_cap_shares < suggested_shares:
            suggested_shares = max(liq_cap_shares, 0)
            suggested_lots = suggested_shares // lot_size
            cost = suggested_shares * entry
            cost_pct = cost / total_capital if total_capital > 0 else 0
            liq_note = f"流動性限縮（≤{max_adv_pct*100:.0f}%日均量）"
            warning = (warning + " | " if warning else "") + liq_note

    if suggested_lots == 0 and raw_shares > 0:
        warning = f"建議股數 {raw_shares:.0f} 不足 1 張，跳過或降低風險%"

    if position_factor < 1.0:
        warning = (warning + " | " if warning else "") + f"大盤調整係數 {position_factor:.1f}"

    return {
        "risk_per_share": round(risk_per_share, 2),
        "max_risk_amount": round(max_risk_amount, 0),
        "raw_shares": int(raw_shares),
        "suggested_shares": int(suggested_shares),
        "suggested_lots": int(suggested_lots),
        "cost": round(cost, 0),
        "cost_pct": round(cost_pct * 100, 2),
        "warning": warning,
    }


def evaluate_add(cfg, current_price, atr, ext_pct, rs, add_lots,
                 lot_size=1000):
    """
    加碼檢查：在現價加碼 add_lots 張是否合理。
    風控優先——過度延伸（追高）一律建議等拉回；並算出加碼後的風險、是否超單筆預算。
    回傳 dict：verdict / 停損 / 風險金額 / 佔資金% / 風險預算內最多可加張數 / 阻擋與警示原因。
    """
    ps = cfg.get("position_sizing", {})
    hcfg = cfg.get("holdings", {})
    atr_mult = cfg.get("filters", {}).get("atr_mult", 1.5)
    cap = ps.get("total_capital", 1_000_000)
    risk_budget = cap * ps.get("risk_per_trade_pct", 0.01)
    ext_max = hcfg.get("add_max_ext_pct", 8.0)
    rs_min = hcfg.get("add_min_rs", -10.0)

    out = {"verdict": "—", "stop": None, "risk_per_share": None,
           "add_risk": None, "add_cost": None, "cost_pct": None,
           "max_lots_in_budget": None, "blocks": [], "warns": []}
    if not current_price or current_price <= 0 or not atr or atr <= 0:
        out["verdict"] = "資料不足"
        return out

    risk_ps = atr * atr_mult
    stop = current_price - risk_ps
    shares = int(add_lots) * lot_size
    add_cost = current_price * shares
    add_risk = risk_ps * shares
    out.update({
        "stop": round(stop, 2),
        "risk_per_share": round(risk_ps, 2),
        "add_risk": round(add_risk, 0),
        "add_cost": round(add_cost, 0),
        "cost_pct": round(add_cost / cap * 100, 1) if cap else None,
        "max_lots_in_budget": int(risk_budget // (risk_ps * lot_size)) if risk_ps > 0 else 0,
    })

    if ext_pct is not None and ext_pct > ext_max:
        out["blocks"].append(f"乖離 MA20 {ext_pct:.1f}% > {ext_max:.0f}%（過度延伸、追高）")
    if rs is not None and rs < rs_min:
        out["warns"].append(f"RS {rs:.0f}（落後股，集中度風險）")
    if add_risk > risk_budget:
        out["warns"].append(
            f"加碼風險 {add_risk:,.0f} 元 > 單筆預算 {risk_budget:,.0f} 元（張數偏多）")

    if out["blocks"]:
        out["verdict"] = "🔴 此價別加 · 等拉回"
    elif out["warns"]:
        out["verdict"] = "🟡 可加但留意（縮量/減張）"
    else:
        out["verdict"] = "🟢 可加"
    return out


def calc_targets(entry, stop):
    """+1R 半倉、+2R 出清"""
    if entry <= 0 or stop >= entry:
        return None, None
    risk = entry - stop
    return round(entry + risk, 2), round(entry + 2 * risk, 2)
