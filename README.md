# 台股波段決策系統

給台股波段散戶的每日決策助手：每天收盤後 10 分鐘，回答「今天能不能做、買哪幾檔、手上哪幾檔該賣」，並追蹤每月目標。

## 七個分頁

| 分頁 | 回答的問題 |
|---|---|
| **今日決策**（首頁） | 今天能不能開新倉？持股要怎麼處理？候選股的完整交易計畫？本月目標進度？ |
| **找標的** | 哪幾檔值得買？（強勢突破 / 早期突破 / 潛伏起漲前三種策略，點一列看入選理由與交易計畫） |
| **個股健檢** | 這檔能不能買、該不該賣？財報與月營收的白話健檢、K 線 |
| **持股與紀錄** | 手上的該不該賣？賣出後記錄，自動扣手續費與證交稅，統計每月損益與勝率 |
| **資金流向** | 美國資金輪動、三大法人、類股成交比重、台美連動 |
| **學習中心** | 交易哲學、財報、營運、股票、總經、名詞表，附月目標與部位計算機 |
| **策略驗證** | 這套策略可信嗎？大樣本實證（核心指標、10 年大盤基準）、回測、自動校準、實戰績效 |

**核心指標：距一年高點**（收盤 ÷ 過去一年最高價）。10 年、1,033 檔上市股比較 8 個常見指標後選出：大盤非空頭時，收盤 ≥ 一年高點 90% 的股票，之後 1 個月平均 +1.61%（扣成本），全部可交易股 +0.51%，每一年都跑贏平均；大盤空頭時沒有優勢。找標的、今日決策都依它排序，個股健檢直接顯示。研究方法與限制見「策略驗證 → 大樣本實證」與 [`scripts/strategy_study/`](scripts/strategy_study/)。

設計原則：風險先於報酬、流程勝過預測、承認不確定。月目標只用來推算要做幾筆與控制風險（每月虧損上限、空頭不開新倉），不用來放大部位。

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
- [docs/DESIGN.md](docs/DESIGN.md) — 設計規範：顏色、數字格式、版面元件、驗收清單
- [docs/DEPLOY.md](docs/DEPLOY.md) — 部署到 Streamlit Community Cloud
- [docs/雲端設定.md](docs/雲端設定.md) — Neon 雲端會員空間（持股 / 日誌永久保存）
- [docs/判讀指南.md](docs/判讀指南.md) — 系統說明與判讀指南
