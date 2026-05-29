# 部署到 Streamlit Community Cloud

## 前置條件
- ✅ Repo 已公開：https://github.com/allens920181/tw-stock-breakout-scanner
- ✅ `app.py` 在 repo 根目錄
- ✅ `requirements.txt` 已產生
- ✅ `.streamlit/config.toml` 已設定

## 部署步驟

### 1. 登入
打開 https://share.streamlit.io，用 GitHub 登入。

### 2. 新增 App
點 **New app**，填入：

| 欄位 | 值 |
| --- | --- |
| Repository | `allens920181/tw-stock-breakout-scanner` |
| Branch | `main` |
| Main file path | `app.py` |
| App URL | 自訂，例如 `tw-stock-scanner` |
| Python version | 3.13（或 3.11、3.12 均可） |

### 3. Deploy
點 **Deploy**。約 3 分鐘內 build 完，可在
`https://tw-stock-scanner.streamlit.app/`（或你選的 URL）開啟。

## 限制與注意事項

### 🔁 Inactivity Sleep
免費版 7 天無人造訪會睡眠。下次造訪者要等 ~30 秒喚醒。

### 💾 檔案系統不持久化
重新部署 / 重啟後**會清空**：
- `.cache/`（OHLC parquet、股數、敏感度結果）
- `~/.tw_scanner_prefs.json`（使用者偏好）
- `.cache/scans/`（歷史掃描記錄）

每次冷啟動使用者要重抓 yfinance 資料。

### 📊 資源限制
- 1 GB RAM
- 1 CPU
- 一次掃描全台股約 5–15 分鐘，可能會超時。**建議使用者先用上傳清單模式（小量檔）**。

## 部署後第一次測試

1. 開啟 URL
2. 側欄：選「上傳清單」→ 下載模板 → 編輯後上傳
3. 點「開始掃描」確認流程
4. 切「持股管理」→ 編輯一檔 → 點「分析持股」確認 yfinance 可正常抓
5. 切「回測」→ 設定 30 天 → 跑回測確認

## 更新流程

```bash
git add .
git commit -m "update"
git push
```

Streamlit Cloud 偵測到 push 會自動 redeploy（約 1-2 分鐘）。

## 如果掃描全台股太慢

可以加 Streamlit secrets 限制掃描範圍，或在側欄加 disabled 提示。

## 切回私有

```bash
gh repo edit allens920181/tw-stock-breakout-scanner --visibility private
```

Streamlit Cloud 公開 plan 不支援私有 repo，切回後 app 會無法 build。
