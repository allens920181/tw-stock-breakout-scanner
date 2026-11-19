# 策略實證研究（2026-11）

回答一個問題：**在實盤會下單的條件下，系統的選股訊號有沒有比隨機進場好？**

結論與數據：[`docs/research/strategy_study_2026-11.json`](../../docs/research/strategy_study_2026-11.json)，App 的「策略驗證 → 大樣本實證」會顯示。

## 重跑

```bash
S=/tmp/study && mkdir -p $S/cache
uv run python scripts/strategy_study/download.py $S/cache $S/data2y.pkl        # 上市普通股 2 年日線（約 5 分鐘）
uv run python scripts/strategy_study/study.py $S/data2y.pkl $S/cache $S/results.json      # 72 種變體
uv run python scripts/strategy_study/baseline.py $S/data2y.pkl $S/cache scripts/strategy_study $S/baseline.json  # 對照：隨機進場
uv run python scripts/strategy_study/rs_test.py $S/data2y.pkl $S/cache scripts/strategy_study $S/rs.json          # 單一假設：相對強度
uv run python scripts/strategy_study/index_timing.py $S/index_timing.json   # 10 年大盤燈號擇時 vs 買進持有
```

## 方法

- 進場條件與實盤一致：股價 ≥ 10、20 日均量 ≥ 500 張、站上 MA60、停損距離 ≥ 2%、大盤非空頭；只用當日以前的資料
- 成本：手續費 0.1425% × 2、證交稅 0.3%、滑價 0.15% × 2；跳空跌破停損以開盤價成交
- 前 70% 交易日為樣本內（挑變體），後 30% 為樣本外（只報告、不再調）
- 對照組：同樣過濾與出場，但進場日隨機、頻率與訊號相同。訊號必須贏過對照組才算有選股能力
