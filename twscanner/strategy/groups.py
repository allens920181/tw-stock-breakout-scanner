# -*- coding: utf-8 -*-
"""
族群（產業）層級的策略後處理 — 跨檔、作用在整批掃描結果上。

- annotate_group_strength：標記同產業強勢檔數（族群同步 = 主流確認）
- apply_sector_heat：同產業進場檔數過多時按比例降碼（控制相關性集中）

產業對照資料由 twscanner.data.sectors.fetch_sectors 提供。
"""


def annotate_group_strength(results, sectors_map):
    """
    跨檔後處理：為每筆結果加上「產業 / 族群強勢檔數 / 族群同步」。
    族群強勢 = 同產業中訊號為「進場」或「觀察」的檔數。
    就地修改 results（list[dict]）。
    """
    from collections import defaultdict
    strong_by_ind = defaultdict(int)
    for res in results:
        sym = str(res.get("股票", ""))
        ind = sectors_map.get(sym.split(".")[0])
        res["產業"] = ind or "—"
        if ind and res.get("訊號判斷") in ("進場", "觀察"):
            strong_by_ind[ind] += 1

    for res in results:
        ind = res.get("產業")
        if ind and ind != "—":
            cnt = strong_by_ind.get(ind, 0)
            res["族群強勢檔數"] = cnt
            res["族群同步"] = f"族群同步{cnt}檔" if cnt >= 2 else "—"
        else:
            res["族群強勢檔數"] = None
            res["族群同步"] = "—"
    return results


def apply_sector_heat(results, heat_max=3):
    """
    組合熱度控制：同產業「進場」檔數超過 heat_max 時，
    對該產業每檔進場部位按比例降碼（heat_max / 進場檔數），避免相關性集中。
    就地修改 results 的 建議張數 / 進場成本 / 佔資金%，並標記提示。
    """
    from collections import defaultdict
    entry_by_ind = defaultdict(list)
    for res in results:
        ind = res.get("產業")
        if ind and ind != "—" and res.get("訊號判斷") == "進場":
            entry_by_ind[ind].append(res)

    for ind, rows in entry_by_ind.items():
        n = len(rows)
        if n <= heat_max:
            continue
        factor = heat_max / n
        for res in rows:
            lots = res.get("建議張數")
            if not lots or lots <= 0:
                continue
            new_lots = int(lots * factor)   # floor
            scale = new_lots / lots if lots else 0
            res["建議張數"] = new_lots
            if res.get("進場成本") is not None:
                res["進場成本"] = round(res["進場成本"] * scale, 0)
            if res.get("佔資金%") is not None:
                res["佔資金%"] = round(res["佔資金%"] * scale, 2)
            note = f"族群減碼 ×{factor:.2f}（{ind}進場{n}檔>上限{heat_max}）"
            existing = res.get("部位提示", "")
            res["部位提示"] = (existing + " · " + note) if existing else note
    return results
