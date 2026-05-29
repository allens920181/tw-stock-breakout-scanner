import os
from datetime import datetime

import pandas as pd


def build_dataframes(results, failed_list, stock_count, elapsed_sec):
    df = pd.DataFrame(results)
    for col in ["評分", "換手率%", "RR比"]:
        if col not in df.columns:
            df[col] = None

    df = df.sort_values(
        by=["評分", "換手率%", "RR比"],
        ascending=[False, False, False],
        na_position="last",
    )

    def _count(label):
        if "訊號判斷" not in df.columns:
            return 0
        return int((df["訊號判斷"] == label).sum())

    summary = pd.DataFrame([{
        "掃描股票數": stock_count,
        "成功分析檔數": int((df.get("狀態", pd.Series(dtype=str)).str.startswith("成功", na=False)).sum()),
        "強勢候選檔數": _count("強勢候選"),
        "觀察檔數": _count("觀察"),
        "偏弱觀察檔數": _count("偏弱觀察"),
        "不符合檔數": _count("不符合"),
        "執行秒數": round(elapsed_sec, 1),
        "策略條件": "突破+量增 / MA多頭 / 換手率強勢 / KD / MACD（加權）",
        "說明": "v3.1 加權評分 + 品質前置過濾 + RR 合理性檢查",
    }])

    failed_df = pd.DataFrame(failed_list)
    return df, summary, failed_df


def write_excel(df, summary, failed_df, output_dir, prefix):
    os.makedirs(output_dir, exist_ok=True)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"{prefix}_{now}.xlsx")
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="全部分析結果", index=False)
        summary.to_excel(writer, sheet_name="Report摘要", index=False)
        if failed_df is not None and len(failed_df) > 0:
            failed_df.to_excel(writer, sheet_name="錯誤清單", index=False)
    return path
