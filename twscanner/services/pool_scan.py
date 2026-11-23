"""
掃描一個範圍（UI 與背景執行共用）：先用今天的資料池，缺的才下載，必要時只更新現價，最後評估。

純函式、不碰 Streamlit，所以可以放到背景執行緒跑；結果由呼叫端（主執行緒）寫回 session。
"""
from twscanner.services.scan import merge_pool, refresh_prices, run_scan, split_by_pool

PRICE_STALE_MIN = 20     # 資料池的現價超過這麼久就重抓現價（只在使用者按「開始掃描」時）


def run_pool_scan(cfg, items, pool, pool_age_min=None, fresh_prices=True, progress_cb=None, scan=run_scan):
    """
    items：[{code, company_name}]；pool：今天的資料池或 None（不會被修改）；pool_age_min：資料池現價的分鐘數。
    progress_cb(pct, msg)。回 {"result", "pool", "pool_changed", "total", "reused", "downloaded"}。
    """
    def cb(stage, pct, msg):
        if progress_cb:
            progress_cb(pct, f"{stage}：{msg}")

    pool = dict(pool) if pool else None
    sub, missing = split_by_pool(pool, items)
    reused = len(items) - len(missing)
    changed = False
    if missing:
        part = scan(cfg=cfg, progress_cb=cb, items=missing)
        pool, changed = merge_pool(pool, part["scan_cache"]), True
        if reused:
            sub, _ = split_by_pool(pool, items)
            result = scan(cfg=cfg, cached=sub, progress_cb=cb)
        else:
            result = part
    else:
        if fresh_prices and (pool_age_min is None or pool_age_min > PRICE_STALE_MIN):
            if progress_cb:
                progress_cb(0.1, f"更新 {len(sub['resolved'])} 檔現價（其他資料沿用今天已下載的）")
            pool["price_map"] = {**pool.get("price_map", {}), **refresh_prices(sub, cfg)}
            changed = True
            sub, _ = split_by_pool(pool, items)
        result = scan(cfg=cfg, cached=sub, progress_cb=cb)
    return {"result": result, "pool": pool, "pool_changed": changed, "total": len(items),
            "reused": reused, "downloaded": len(missing)}
