# 台股波段決策系統

給台股波段散戶的每日決策助手：每天收盤後 10 分鐘，回答「今天能不能做、買哪幾檔、手上哪幾檔該賣」，並追蹤每月目標。

## 八個頁面

| 分頁 | 回答的問題 |
|---|---|
| **今日決策**（首頁） | 今天能不能開新倉？持股要怎麼處理？候選股的完整交易計畫？本月目標進度？ |
| **找標的** | 哪幾檔值得買？（強勢突破 / 早期突破 / 潛伏起漲前三種策略，點一列看入選理由與交易計畫） |
| **個股健檢** | 這檔能不能買、該不該賣？財報與月營收的白話健檢、K 線 |
| **持股與紀錄** | 手上的該不該賣？賣出後記錄，自動扣手續費與證交稅，統計每月損益與勝率 |
| **資金流向** | 美國資金輪動、三大法人、類股成交比重、台美連動 |
| **學習中心** | 交易哲學、財報、營運、股票、總經、名詞表，附月目標與部位計算機 |
| **策略驗證** | 這套策略可信嗎？大樣本實證（核心指標、10 年大盤基準）、回測、自動校準、實戰績效 |
| **設定** | 資金與月目標、漲跌顏色、雲端帳號、進階選股條件 |

**核心指標：距一年高點**（收盤 ÷ 過去一年最高價）。10 年、1,033 檔上市股比較 8 個常見指標後選出：大盤非空頭時，收盤 ≥ 一年高點 90% 的股票，之後 1 個月平均 +1.61%（扣成本），全部可交易股 +0.51%，每一年都跑贏平均；大盤空頭時沒有優勢。找標的、今日決策都依它排序，個股健檢直接顯示。研究方法與限制見「策略驗證 → 大樣本實證」與 [`scripts/strategy_study/`](scripts/strategy_study/)。

**實證規則：距一年高點 ＋ 月營收驚喜**。投資組合實測（2005–2026、扣成本）顯示，單看「距一年高點」沒有穩定贏過 0050；加上月營收驚喜、每月營收公布後換股、持有 20 檔，全期年化 25.5%，同期 0050 含息 13.6%，停損與大盤擇時都沒有加分。規則、目前名單與限制在「策略驗證 → 實證規則」，完整報告見 [`reports/台股波段買賣規則實證研究.md`](reports/台股波段買賣規則實證研究.md)。回測不是保證：只含仍上市的股票、最大回撤 −32%。

**背景與排程**：按「開始掃描」後掃描在背景執行，切換頁面不會中斷、完成自動載入；也可以由 GitHub Actions 每個交易日收盤後自動跑、結果存雲端，打開 App 直接載入。設定見 [docs/排程掃描.md](docs/排程掃描.md)。

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

App 裡在「找標的」頁上方的「範圍」選「全台股」即可。

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
├── ui/         Streamlit：外殼（頂部導覽）、掃描列、元件、pages/ 各頁
└── cli.py
tests/          單元測試 + test_architecture.py（分層守門）
docs/           架構、部署、雲端設定、判讀指南
```

分層規則、各層職責、以及「新增資料源 / 策略 / 分頁」的步驟見 **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**。

## 評分與過濾參數

評分權重、進場/觀察門檻、品質過濾、風格 Preset、交易成本等**全部以 [`config.yaml`](config.yaml) 為準**，
可在「設定」頁的「進階：選股條件」微調。各指標的意義與判讀方式見 [docs/判讀指南.md](docs/判讀指南.md)。

## 文件

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 工程架構與開發指南
- [docs/DESIGN.md](docs/DESIGN.md) — 設計規範：顏色、數字格式、版面元件、驗收清單
- [docs/DEPLOY.md](docs/DEPLOY.md) — 部署到 Streamlit Community Cloud
- [docs/排程掃描.md](docs/排程掃描.md) — 背景掃描與自動排程
- [docs/雲端設定.md](docs/雲端設定.md) — Neon 雲端會員空間（持股、交易紀錄、日誌、設定自動同步）
- [docs/判讀指南.md](docs/判讀指南.md) — 系統說明與判讀指南
