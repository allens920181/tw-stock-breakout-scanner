# 設計規範（給改 UI 的人）

完整的研究、診斷與理由在 [設計基準 v1](https://claude.ai/artifact/5PLXfwtPYeEmNbryDm96cQ) 與 [重大升級規劃 v2](https://claude.ai/artifact/DoDPsYxCqxxNsGnwAiMAcv)。這份只列寫程式時要遵守的規則，以及它們在程式碼裡的位置。

## 1. 產品原則

產品定位：台股波段散戶的每日決策助手，30 秒內回答「今天能不能做、買哪幾檔、手上哪幾檔該賣」。兩個方向衝突時，依下列順序取捨：

1. 一個問題只有一個答案（同一檔在任何頁面的建議一致；缺資料時寫出假設）
2. 一種顏色只有一個意思
3. 先結論、再理由、最後資料
4. 預設簡單，進階收合
5. 數字要能比較
6. 誠實優先於好看（樣本數、信賴區間、資料時間貼在數字旁）

## 2. 顏色（`twscanner/ui/format.py`、`theme.py`）

| 群組 | Token | 用在 | 不可用在 |
|---|---|---|---|
| 方向 | `up` / `down`（預設紅漲綠跌，可切換） | 漲跌、損益、買賣超、多空燈號、RRG 領先/落後 | 錯誤、成功、按鈕 |
| 狀態 | `caution`、`critical`、`info`、`flat` | 要賣/減半、樣本不足、錯誤、說明、中性 | 漲跌方向 |
| 品牌 | `primary` 墨黑 `#18181B` | 主按鈕、目前頁、圖表重點（其餘用灰 `#D4D4D8`） | 任何漲跌數字 |

- 程式裡要漲跌色一律呼叫 `colors()` / `dir_color()`，不寫死 hex，切換綠漲紅跌才會全站一致。
- 方向色一定搭配第二線索（+/− 號或文字），紅綠色弱也看得懂。
- 不在文字裡用 🟢🔴 表示多空（在台股語意下會與顏色相反）；需要時用 `strip_icon()` 去掉資料裡的 emoji。

## 3. 數字（`format.py`）

| 類型 | 函式 | 例 |
|---|---|---|
| 股價 | `fmt_price` | 2,175.00 |
| 漲跌幅、報酬 | `fmt_pct` | +7.69%、−1.01% |
| 金額 | `fmt_money` | +372,000 元 |
| 億元 | `fmt_yi` | −243.1 億 |
| R 倍數 | `fmt_r` | +1.35R |
| 股票 | `stock_label` / `clean_stock_col` | 2330 台積電（不顯示 .TW） |

表格用 `st.column_config.NumberColumn` 的 format；千分位用 `"localized"`（Streamlit 的 printf 格式不支援 `,`）。

## 4. 版面

### 架構（`ui/app.py`，參考券商 App 與 Stripe / Linear 類儀表板）

- **頂部導覽**（`st.navigation(position="top")`）+ 左上角品牌，沒有常駐側欄。只有目前這頁會執行。
- **每天要用的控制項放在頁面裡**：掃描的範圍 / 策略 / 風格 / 開始掃描是「找標的」頁頂端的一列（`ui/scan_controls.py`），每顆是「標籤 · 目前值」的彈出選單。
- **不常改的放「設定」頁**（`pages/settings_page.py`）：資金與月目標、漲跌顏色、雲端帳號、進階選股條件。
- **頁首**（`components/header.py`）：頁名與日期在左，台股 / 美股 / 大資金三個狀態在右（文字 + 小圓點），下面一行白話建議（今日決策、找標的的結論句已經說了，就不重複）。
- 今日決策桌機分兩欄：左邊是要動手的（持股、候選），右邊是參考（本月目標、交易紀律）；手機自動疊成一欄。
- 個股健檢用報價式頁首：名稱代號 → 大字股價與漲跌 → 結論。
- 跨頁保留的設定值列在 `state.PERSIST_KEYS`；widget 只給 `key`、用 `state.seed()` 帶預設值，不要同時給 `value`（會跳警告）。

### 視覺：去掉「樣板感」

- **用淺灰填色與留白分區，不用框線**：卡片、KPI、收合區塊、輸入框都是 `#F5F5F6` 底、圓角 12px、無框。
- **不用卡片左側色條**：狀態改用結論句上方的小標籤（可行動 / 注意 / 觀望）或淡底色提示。
- **按鈕沒有細框**：主按鈕墨黑實心；次按鈕淺灰實心；分段選擇是灰色軌道 + 白色選中塊。
- 清單用細分隔線（`#ECECEE`），表格不加外框。
- `tests/test_ui_theme.py` 把關：CSS 不得出現 `border-left`、按鈕規則不得有框線、品牌色不是靛藍。

### 每頁的順序（`components/blocks.py`）

每頁由上而下：**結論句 → KPI（最多 4 個）→ 主體 → 進階（收合）**。

| 元件 | 函式 | 規則 |
|---|---|---|
| 結論句 | `conclusion(lead, sub, tone)` | 第一行就是答案，最好帶數字；tone：go / stop / wait / info |
| KPI 列 | `kpi_row([(label, value, sub)])` | 不重複指標；長文字放結論句不放 KPI |
| 等級、動作徽章 | `grade_badge`、`action_badge` | 全站同一外觀 |
| 交易計畫卡 | `plan_card(plan)` + `buy_form` | 進場、停損、目標、張數、最多賠多少、入選理由、出場規則 |
| 空狀態 | `empty(title, body)` | 說「為什麼」與「下一步」，提到的功能必須存在 |
| 資料時間 | `asof(text)` | 每個數據區塊都標；完成後不留進度條（用 `st.status`） |

所有資料文字放進 HTML 前都要跳脫（`html.escape`）：指標說明常含 `<` 符號，會被瀏覽器當成標籤吃掉。

## 5. Streamlit 的坑（都踩過）

- **CSS 注入**：以 `<link>` 開頭的 Markdown HTML 區塊遇空行就結束；`theme._html_block()` 處理，`tests/test_ui_theme.py` 把關。
- **pandas 3 的字串用 pyarrow（RE2）**，`\w` 只認 ASCII，`.str.replace(r"\w…")` 會把中文刪掉。用 Python `re`（`strip_icon`）。
- **所有分頁每次都會重跑**，而且由左到右畫；後面分頁產生的資料（掃描、回測）存好後要 `st.rerun()`，前面的今日決策才會更新。
- **`st.cache_data` 會快取「抓不到」的結果**；暫時失敗時丟例外（`state._NotReady`），不要回傳 unknown。
- **分段選擇（`st.segmented_control`）要加 `required=True`**：否則再點一次已選的選項會變成「沒選」，下面的內容跟著消失。
- **上傳檔用 `on_change` 存起來**：在 callback 裡存，重畫前就生效，按鈕標籤才會顯示新檔名。
- **多頁導覽下，不在本頁的 widget 值會被清掉**：要跨頁保留就加進 `state.PERSIST_KEYS`；上傳檔存成 bytes（`scan_controls._Upload`）。
- **公開部署時伺服器檔案是所有訪客共用的**：個人資料（持股、交易）只放 session 或登入後的雲端。

## 6. 手機版（iPhone 寬度 390px）

- 頂部導覽在手機會收進側邊選單，**右上角「☰」是入口**（`stExpandSidebarButton` 改成選單圖示並固定在右上）。不可用 CSS 隱藏 `stToolbar` 或這顆按鈕（`tests/test_ui_theme.py` 把關）。
- `st.columns` 在 640px 以下會疊成一欄：KPI 用 `kpi_row`（CSS grid，手機自動 2×2）；掃描控制列用 `.st-key-scanbar` 排成 2×2；表單用「一列一組」的 columns，疊起來順序才對。按鈕列控制在 2 顆，其餘收進 popover。
- 分頁列不換行、可橫向滑動（換行時 BaseWeb 的選取底線會畫在錯的分頁下）。
- 圖表用 `components.charts.plot(fig)`：標題移到圖外才會換行；圖內文字與座標軸標題要短。
- 驗收時用 Playwright 的 `devices['iPhone 13']` 跑完整流程（換頁要點導覽，不要重新載入網址，否則會開新 session），並檢查 `scrollWidth <= innerWidth`（不得橫向捲動）。

## 7. 驗收

改完 UI，合併前逐項確認：

1. 首屏第一句是結論，且帶數字
2. 漲跌、損益、買賣超都用 `up`/`down`，帶 +/− 或文字
3. 紅綠沒有用在錯誤、成功、提醒或按鈕
4. 同類數字格式一致、靠右、等寬
5. 股票顯示「代號 名稱」
6. KPI 一列最多 4 個、不重複、不截斷
7. 一個區塊最多一個提示框
8. 空狀態與查無結果都有「為什麼 + 下一步」
9. 數據區塊標「資料截至」，沒有殘留進度條
10. 同一檔在個股健檢與持股給相同建議
11. 文案提到的按鈕與分頁都存在
12. 手機 390px 首屏看得到市場狀態與結論句，沒有橫向捲動
13. 沒有框線按鈕、沒有卡片左側色條
14. 桌機與手機各截一張圖，與改版前並排比對
15. `uv run pytest` 與 `uv run ruff check .` 通過
