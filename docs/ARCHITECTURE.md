# 工程架構

> 目標：**好維護**（改一處不牽動全身）、**好擴展**（新資料源 / 新策略 / 新分頁有固定放法）、**好開發**（可測、可 lint、CI 把關）。

## 一、全貌

```
app.py                 Streamlit 入口（10 行，Streamlit Cloud 指向此檔）
main.py                CLI 入口（5 行）
config.yaml            所有策略 / 資料 / 輸出參數（唯一的參數來源）
twscanner/
├── core/              基礎設施：設定載入、當日快取、台灣時區
├── data/              外部資料來源（只抓 + 解析）：價格、清單、法人、融資、營收、財報、財務報表、產業、名稱
├── analysis/          純計算（無 I/O）：技術指標、進場分類、部位、統計檢定、財報健檢、月目標
├── strategy/          選股策略：強勢/早期突破評分、潛伏模式、族群強勢/熱度
├── market/            市場層級判斷：台股大盤、美股風險、大資金、資金流向
├── portfolio/         持股出場建議、訊號日誌、已實現交易紀錄、組合風險
├── research/          回測、因子驗證、敏感度、自適應參數
├── storage/           持久化：雲端（Neon）、掃描歷史、使用者偏好、交易紀錄（僅雲端）
├── reporting/         輸出：Excel 報告、K 線圖
├── services/          應用流程：掃描、單檔健檢、持股分析、研究、今日決策 —— GUI 與 CLI 共用
├── ui/                Streamlit 介面
│   ├── app.py         外殼：頁面設定 → 狀態 → 樣式 → 頂部導覽 → 頁首 → 目前頁（PAGES 註冊表、錯誤隔離）
│   ├── state.py       快取載入、雲端/偏好 bootstrap、持股與交易紀錄的 session 存取
│   ├── settings.py    設定值 → 掃描 cfg（build_run_config 為純函式）
│   ├── actions.py     跨頁共用的動作：執行掃描、分析持股、用快取重算
│   ├── format.py      數字格式與漲跌色（紅漲綠跌 / 綠漲紅跌）—— 全站唯一來源
│   ├── scan_controls.py 找標的頁頂端的掃描列；current_scan_state() 給其他頁用
│   ├── theme.py       CSS token 與樣式
│   ├── glossary.py    名詞說明（help tooltip 與學習中心名詞表共用）
│   ├── components/    blocks（結論句、KPI、徽章、交易計畫卡、空狀態）、頁首、圖表
│   └── pages/         today / scan / lookup / holdings / flows / learn / research（+ backtest、history 子頁）
└── cli.py             命令列介面
tests/                 單元測試 + 架構守門測試（test_architecture.py）
docs/                  架構、設計規範、部署、雲端設定、判讀指南
```

## 二、分層規則（由 `tests/test_architecture.py` 自動檢查）

依賴只能**往下**，不能往上或橫跳：

```
            ui            cli
              \           /
               services
     /     /      |       \        \
research  portfolio  storage  reporting
   |   \      |
strategy  market
     \   /
  data   analysis
      \   /
      core
```

| 層 | 可以 import |
|---|---|
| `core` | 只有自己 |
| `data` / `analysis` / `storage` | `core` |
| `strategy` / `market` / `portfolio` | `core`、`data`、`analysis` |
| `reporting` | `core`、`analysis` |
| `research` | 上述 + `strategy`、`market` |
| `services` | 除了 `ui`、`cli` 以外全部 |
| `ui` | 除了 `cli` 以外全部 |
| `cli` | `core`、`data`、`reporting`、`services` |

另外兩條硬規則：

- **只有 `ui/` 可以 `import streamlit`。** 其他層都要能在 CLI、測試、排程中執行。
- **一律使用絕對 import**（`from twscanner.data.chips import fetch_chips`），不用相對 import。

違規時 `pytest` 會直接列出檔案、行號與違規方向。

### 為什麼這樣分

- **`data` 與 `analysis` 分開**：抓資料會壞（網站改版、限流），計算不該跟著壞；純計算也才好寫單元測試。
- **`services` 是唯一的組裝點**：GUI 和 CLI 都只呼叫 `twscanner.services`，所以同一份掃描邏輯不會在兩個介面各寫一次。
- **`ui/pages` 各自獨立**：每頁一個檔案，彼此不 import；共用的東西放 `components/` 或 `state.py`。單一分頁出錯時，外殼會隔離錯誤，不會讓其他分頁消失。

## 三、常見擴展怎麼做

### 新增一個資料來源（例如：借券賣出）

1. `twscanner/data/sbl.py`：只負責抓 + 解析，回傳 dict / DataFrame；失敗回空值，不要拋例外中斷掃描。
2. 要快取就用 `twscanner.core.cache`（當日有效）。
3. 把解析寫成純函式（輸入 JSON 或文字 → 輸出結構），在 `tests/` 用假資料測。
4. 在 `services/scan.py` 呼叫並把結果交給策略層。

### 新增一個選股策略模式

1. `twscanner/strategy/<mode>.py`：提供 `analyze_<mode>(...)`，回傳與 `scoring.analyze_stock` 相同欄位的 dict。
2. 在 `services/scan.py` 的 `analyze_fn` 分派處（目前 `ambush` → `analyze_ambush`，其餘 → `analyze_stock`）加上新模式。
3. 參數放進 `config.yaml` 的 `strategy.<mode>`。
4. 在 `ui/scan_controls.py` 的 `MODE_LABELS` / `MODE_HELP` 加上名稱與說明。

### 新增一個分頁

1. `twscanner/ui/pages/<name>.py`，提供 `render()`；版面照 [DESIGN.md](DESIGN.md)：結論句 → KPI → 主體 → 進階；若需要掃描設定（資料來源等），改成 `render(sb)`，`sb` 是 `ScanState`。
2. 在 `twscanner/ui/app.py` 的 `PAGES` 加一行 `(網址, 導覽名稱, 頁首標題, 模組, 是否需要掃描設定)`。
3. 重的運算放在 `services/` 或 `market/`，並在頁面用 `st.cache_data` 包住。Streamlit 每次互動都會重跑目前這一頁，避免在 `render()` 裡直接抓網路資料。

### 新增設定

1. 在 `ui/pages/settings_page.py` 加 widget，用 `key=seed("名稱", 預設值)`（不要再給 `value`），並把 key 加進 `state.PERSIST_KEYS`。
2. 在 `ui/settings.py` 的 `build_run_config` 把該 key 對應進 cfg。
3. 在 `tests/test_ui_settings.py` 加一個斷言。

### 掃描資料池（換範圍不用重抓）

`services/scan.py` 的 `split_by_pool` / `merge_pool`：每次掃描下載到的原始資料（價格歷史、股數、現價、財報日，以及全市場的籌碼、融資、營收、大盤）併進「當日資料池」（`state.current_pool`，跨日作廢）。

- 掃描時先從池子切出範圍內的股票，**只下載池子裡沒有的**。
- 換範圍時（`pages/scan.py::_scope_changed`）：池子已涵蓋 → 自動重算，不用按按鈕；沒涵蓋 → 提示「幾檔沿用、只需下載幾檔」。
- 使用者按「開始掃描」且池子的現價超過 20 分鐘 → 只重抓現價（`refresh_prices`）；價格歷史本來就以日為單位快取在磁碟。

## 四、開發流程

```bash
uv sync                                   # 安裝（含 dev：pytest、ruff）
uv run streamlit run app.py               # 啟動 GUI
uv run python main.py --help              # CLI
uv run pytest                             # 測試（含分層規則）
uv run ruff check . --fix                 # lint + 自動排序 import
```

CI（`.github/workflows/ci.yml`）在每次 push 到 `main` 與每個 PR 執行：`ruff check`、`pytest`，並確認 `requirements.txt` 與 `uv.lock` 同步。

### 改相依套件

Streamlit Cloud 讀的是 `requirements.txt`，所以改完 `pyproject.toml` 後：

```bash
uv lock
uv export --no-dev --no-hashes --format requirements-txt -o requirements.txt
```

## 五、執行期狀態放在哪

| 資料 | 位置 | 生命週期 |
|---|---|---|
| 行情 / 籌碼 / 營收等 | `.cache/*_{YYYYMMDD}.*` | 當日有效 |
| 資金流向的 TWSE 歷史 | `.cache/flows_twse_hist.json` | 依日期永久累積（最多 200 筆） |
| 掃描歷史 | `.cache/scans/` | 保留最近 30 次 |
| 一般偏好（風格、漲跌顏色、上次校準日） | `~/.tw_scanner_prefs.json` | 永久（雲端部署重啟會清空） |
| 財務偏好（總資金、月目標、虧損上限） | Neon `tw_kv`（登入後） | 永久；未登入時只在 session，不寫伺服器檔案 |
| 持股 / 訊號日誌 / 交易紀錄（雲端） | Neon `tw_kv` 表 | 永久，見 [雲端設定](雲端設定.md) |
| 交易紀錄（未登入） | `st.session_state` | 只在該瀏覽器分頁；刻意不寫伺服器檔案（公開部署會被其他訪客看到） |
| UI 狀態 | `st.session_state` | 單一瀏覽器 session |
