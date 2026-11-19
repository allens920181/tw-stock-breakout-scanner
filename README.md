# 台股強勢突破交易清單（換手率版）

掃描 `stock_list.xlsx` 中的股票，依加權評分 + 品質過濾輸出 Excel 報告。

## 特色
- 自動判斷上市 (.TW) / 上櫃 (.TWO)
- 批次下載 + 平行抓股數 + Parquet 本地快取
- 加權評分（突破+量增、MA 多頭、換手率強勢、KD、MACD）
- 品質前置過濾（最低股價、流動性、MA60 趨勢、停損距離）
- **大盤狀態判斷**（^TWII regime）自動調整部位
- **進場類型分類**：突破 / 拉回 / 區間突破
- **部位管理**：固定風險法，自動計算建議買入張數
- **持股管理**：上傳持股 Excel，輸出個股賣出建議（停損/+1R 半倉/+2R 出清/時間停損/移動停利）
- **💰 資金流向分頁**：美股類股輪動圖（RRG）+ 跨資產（股/債/金/美元/幣）+ 風險胃口比值；台股三大法人金額、類股成交比重變化、外資/投信產業別買賣超；台股 vs 前一晚美股/費半連動統計與台積電 ADR 溢價（僅觀測，不影響掃描）
- **Walk-forward 回測**：勝率 / 平均 R / 期望值 / 最大回撤
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
# 用本地清單
uv run python main.py -i stock_list.xlsx

# 掃描全台股（上市+ETF，自動抓 TWSE OpenAPI）
uv run python main.py --universe twse

# 僅 ETF
uv run python main.py --universe twse-etf

# 回測（過去 120 日 walk-forward，持有 10 日）
uv run python main.py --backtest --lookback-days 120 --hold-days 10
uv run python main.py --backtest --universe twse --min-score 6
```

## 掃描全台股

由 [TWSE OpenAPI](https://openapi.twse.com.tw) 抓當日所有上市證券，自動過濾 TDR/特別股/受益證券。
首次約 **5~15 分鐘**（含批次下載 + 抓股數），同日重跑 **<1 分鐘**（讀本地 Parquet 快取）。

GUI 端在側欄選「掃描全台股」即可。

報告輸出檔名格式：`台股全部分析報告_自動判斷市場_YYYYMMDD_HHMMSS.xlsx`

## 開發

```bash
uv sync                      # 安裝（含 pytest、ruff）
uv run pytest                # 測試（含分層架構規則）
uv run ruff check . --fix    # lint + import 排序
```

CI 會在 push 到 `main` 及每個 PR 自動跑 lint 與測試。

## 專案結構

```
app.py          Streamlit 入口      main.py      CLI 入口      config.yaml   全部參數
twscanner/
├── core/       設定、快取、時區
├── data/       外部資料來源（價格、法人、融資、營收、財報、產業）
├── analysis/   純計算（指標、進場分類、部位、統計）
├── strategy/   選股策略（突破評分、潛伏、族群）
├── market/     大盤 / 美股 / 大資金 / 資金流向
├── portfolio/  持股出場建議、訊號日誌
├── research/   回測、因子驗證、敏感度、自適應
├── storage/    雲端、歷史、偏好
├── reporting/  Excel、K 線圖
├── services/   掃描 / 查詢 / 持股 / 研究流程（GUI 與 CLI 共用）
├── ui/         Streamlit：外殼、側欄、元件、pages/ 各分頁
└── cli.py
tests/          單元測試 + test_architecture.py（分層守門）
docs/           架構、部署、雲端設定、判讀指南
```

分層規則、各層職責、以及「新增資料源 / 策略 / 分頁」的步驟見 **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**。

## 評分與過濾參數

評分權重、進場/觀察門檻、品質過濾、風格 Preset、交易成本等**全部以 [`config.yaml`](config.yaml) 為準**，
側欄可即時微調。各指標的意義與判讀方式見 [docs/判讀指南.md](docs/判讀指南.md)。

## 文件

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 工程架構與開發指南
- [docs/DEPLOY.md](docs/DEPLOY.md) — 部署到 Streamlit Community Cloud
- [docs/雲端設定.md](docs/雲端設定.md) — Neon 雲端會員空間（持股 / 日誌永久保存）
- [docs/判讀指南.md](docs/判讀指南.md) — 系統說明與判讀指南
