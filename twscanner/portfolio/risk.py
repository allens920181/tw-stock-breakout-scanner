"""
組合風險（投資經理視角）：所有持股同時打到停損，總共會賠多少？集中在哪個產業？

open risk = (目前價 − 停損價) × 股數；已跌破停損的部位 risk 以 0 計，但列入「應立即處理」。
"""
import pandas as pd


def portfolio_risk(rows, capital, max_risk_pct=5.0, max_positions=5, sector_map=None):
    """
    rows: 持股分析結果（list[dict] 或 DataFrame），需有 股票、目前價、停損價、持有股數。
    回 {total_risk, risk_pct, positions, per, below_stop, by_sector, warnings, ok}
    """
    if isinstance(rows, pd.DataFrame):
        rows = rows.to_dict("records")
    per, below, by_sector = [], [], {}
    for r in rows or []:
        try:
            px, stop, sh = float(r.get("目前價")), float(r.get("停損價")), float(r.get("持有股數") or 0)
        except (TypeError, ValueError):
            continue
        if sh <= 0:
            continue
        code = str(r.get("股票", "")).split(".")[0]
        risk = max(0.0, (px - stop) * sh)
        if px <= stop:
            below.append(code)
        per.append({"股票": code, "公司名稱": r.get("公司名稱"), "到停損風險": risk,
                    "部位市值": px * sh})
        sec = (sector_map or {}).get(code)
        if sec:
            by_sector[sec] = by_sector.get(sec, 0) + 1
    total = sum(p["到停損風險"] for p in per)
    pct = total / capital * 100 if capital else None
    warnings = []
    if pct is not None and pct > max_risk_pct:
        warnings.append(f"全部打到停損會賠 {pct:.1f}% 資金，超過上限 {max_risk_pct:.0f}%，先不要開新倉。")
    if len(per) > max_positions:
        warnings.append(f"同時持有 {len(per)} 檔，超過 {max_positions} 檔上限，照顧不過來。")
    if below:
        warnings.append(f"{'、'.join(below)} 已在停損價之下，應優先處理。")
    crowded = [s for s, n in by_sector.items() if n >= 3]
    if crowded:
        warnings.append(f"{'、'.join(crowded)} 持有 3 檔以上，同漲同跌風險高。")
    return {"total_risk": total, "risk_pct": pct, "positions": len(per), "per": per,
            "below_stop": below, "by_sector": by_sector, "warnings": warnings,
            "ok": not warnings, "max_risk_pct": max_risk_pct, "max_positions": max_positions}
