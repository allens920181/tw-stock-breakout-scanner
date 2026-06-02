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


def calc_targets(entry, stop):
    """+1R 半倉、+2R 出清"""
    if entry <= 0 or stop >= entry:
        return None, None
    risk = entry - stop
    return round(entry + risk, 2), round(entry + 2 * risk, 2)
