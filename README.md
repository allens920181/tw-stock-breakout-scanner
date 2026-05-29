# 台股強勢突破交易清單（換手率版）

掃描 `stock_list.xlsx` 中的股票，依加權評分 + 品質過濾輸出 Excel 報告。

## 特色
- 自動判斷上市 (.TW) / 上櫃 (.TWO)
- 批次下載 + 平行抓股數 + Parquet 本地快取
- 加權評分（突破+量增、MA 多頭、換手率強勢、KD、MACD）
- 品質前置過濾（最低股價、流動性、MA60 趨勢、停損距離）
- 評分分級：強勢候選 / 觀察 / 偏弱觀察 / 不符合
- 自動計算進場價、停損價、目標價、RR 比
- 全參數由 `config.yaml` 控制

## 安裝

```bash
uv sync
```

## 使用

1. 建立 `stock_list.xlsx`，欄位：`股票代號`、`公司名稱`
2. （可選）調整 `config.yaml`

### 方式 A — GUI（推薦）

```bash
uv run streamlit run app.py
```

瀏覽器自動開啟介面：上傳清單、調整參數（過濾門檻、評分權重、分級門檻）、即時進度、結果表格篩選排序、下載 Excel。

### 方式 B — CLI

```bash
uv run python main.py
uv run python main.py -i my_list.xlsx -c my_config.yaml --min-score 5 --log-file run.log
```

報告輸出檔名格式：`台股全部分析報告_自動判斷市場_YYYYMMDD_HHMMSS.xlsx`

## 測試

```bash
uv run pytest
```

## 專案結構

```
.
├── app.py               # Streamlit GUI
├── main.py              # CLI 入口
├── config.yaml          # 策略 / 資料 / 輸出參數
├── src/
│   ├── config.py        # 讀 yaml
│   ├── cache.py         # 本地 Parquet 快取
│   ├── fetcher.py       # yfinance 批次下載 + 平行抓股數
│   ├── indicators.py    # MA / KD / MACD
│   ├── scoring.py       # 過濾 + 加權評分
│   ├── report.py        # Excel 輸出
│   └── runner.py        # 共用掃描流程（GUI/CLI）
└── tests/
    ├── test_fix_code.py
    ├── test_indicators.py
    └── test_scoring.py
```

## 加權評分（總分 8）

| 條件 | 權重 | 說明 |
| --- | --- | --- |
| 突破+量增 | 2 | Close > 20 日高 **且** Volume > 20 日均量 × 1.2 |
| MA 多頭 | 2 | MA5>MA20>MA60 **且** Close>MA20 |
| 換手率強勢 | 2 | 換手率 > 1% **且** > 20 日平均換手率 |
| KD 強勢 | 1 | K > D **且** K > 70 |
| MACD 多方 | 1 | OSC > 0 |

預設門檻：≥6 強勢候選、≥5 觀察、≥4 偏弱觀察。

## 品質前置過濾（預設值，於 `config.yaml` 調整）

- `min_price: 10` — 股價過低直接排除
- `min_avg_volume: 500000` — 20 日均量 < 500 張排除
- `require_above_ma60: true` — 必須站上 MA60
- `min_risk_pct: 0.02` — 停損距離 < 2% 視為訊號降級
