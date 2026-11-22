# Portfolio construction for a concentrated long-only momentum portfolio, and backtest-validity standards (Taiwan retail, as of Nov 2026)

Reader's guide to evidence labels used below:
- **[TW]** = Taiwan-specific evidence. **[US]** / **[Global]** = non-Taiwan evidence.
- **[verified]** = number seen in a source fetched/searched this session. **[recalled]** = number I am confident of from the literature but did NOT re-read this session; the linked source is the right paper but the report writer should treat the exact figure as needing a spot check.
- **[own calc]** = arithmetic done by me from stated assumptions (formula given so it can be re-run). These are in "Inferences", never in "Cited Findings".

---

## A1. How many stocks? Idiosyncratic risk vs number of holdings; probability a small basket underperforms

### Takeaway
With a true edge of ~1 pp/month, a 5-stock book has roughly a 41-43% chance of trailing the market in any month and a 22-29% chance of trailing over a full year purely from stock-specific noise; 20-30 names cut the one-year figure to roughly 3-10% from stock-specific noise alone, but a non-diversifiable "momentum-style" tracking error (~3%/month) puts a floor of ~15% on one-year underperformance no matter how many names are held. Because individual-stock returns are strongly right-skewed (most stocks lose to the index), small baskets are worse than the normal approximation implies: the median small basket misses the few big winners.

### Cited Findings
- **[US][recalled]** Statman (1987, JFQA) concluded a well-diversified portfolio of randomly chosen stocks needs at least 30 stocks for a borrowing investor and 40 for a lending investor, overturning Evans & Archer (1968), who concluded ~10 stocks suffice. **[verified: the 30/40 and ~10 conclusions]** — [Statman 1987, IDEAS](https://ideas.repec.org/a/cup/jfinqa/v22y1987i03p353-363_01.html)
- **[US][recalled — Statman Table 1, not re-read this session]** Expected annual standard deviation of an equal-weight random portfolio: 1 stock 49.2%; 10 stocks 23.9%; 20 stocks 21.7%; 30 stocks 20.9%; 50 stocks 20.2%; 100 stocks 19.7%; infinite 19.2%. I.e. going from 10 to 30 names removes ~3 pp of annual volatility; 30 to infinity only ~1.7 pp. — [Statman 1987, Cambridge PDF](https://www.cambridge.org/core/services/aop-cambridge-core/content/view/CE5CDF2C7225FC1E0EDE3E700A3C66A7/S0022109000012680a.pdf/how_many_stocks_make_a_diversified_portfolio.pdf)
- **[US][verified]** Later work found Statman's required portfolio size depends on the benchmark portfolio size and assumed transaction fees (so "30" is not a constant of nature). — [search summary of follow-up, UGA Financial Services Review](https://openjournals.libs.uga.edu/fsr/article/download/3710/3191)
- **[US][verified]** Campbell, Lettau, Malkiel & Xu (2001, J. Finance; sample 1962-1997): firm-level volatility rose relative to market volatility, correlations among individual stocks fell, and "the number of stocks needed to achieve a given level of diversification has increased"; the standard deviation of a typical 50-stock portfolio rose only modestly over time while a typical 2-stock portfolio rose dramatically. — [NBER Digest](https://www.nber.org/digest/jun00/individual-stocks-have-become-more-volatile); [J. Finance record](https://econpapers.repec.org/RePEc:bla:jfinan:v:56:y:2001:i:1:p:1-43)
- **[US][verified in part]** Bessembinder (2018, JFE, "Do Stocks Outperform Treasury Bills?", CRSP 1926-2016): the best-performing ~4% of listed companies (1,092 firms) account for all net wealth creation over T-bills; 90 firms (~0.3%) account for over half. — [ASU summary page](https://wpcarey.asu.edu/department-finance/faculty-research/do-stocks-outperform-treasury-bills); [ASU news](https://news.wpcarey.asu.edu/20181212-research-shows-most-stocks-haven%E2%80%99t-outperformed-treasury-bills)
- **[Global][verified]** Bessembinder, Chen, Choi & Wei (2023, Financial Analysts Journal; ~64,000 stocks, 1990-2020): 55.2% of US stocks and 57.4% of non-US stocks underperform one-month US T-bills in compound return over the full sample; the top 2.4% of firms account for all net global wealth creation. The 2019 working-paper version (1990-2018) reported only 40.5% of global stocks (43.7% US, 39.3% non-US) beat T-bills. Country share of stocks beating T-bills ranges from 22.8% (Greece) to 67.7% (Colombia); more than half of stocks beat T-bills in only 7 of 42 countries. — [CFA Institute / FAJ 2023](https://rpc.cfainstitute.org/research/financial-analysts-journal/2023/long-term-shareholder-returns-evidence-from-64000-global-stocks); [CXO Advisory summary](https://www.cxoadvisory.com/equity-premium/t-bills-beat-most-global-stocks/)
- **[TW][verified, issuer marketing data — methodology not disclosed]** Cathay SITE analysis of ~2,000 Taiwan stocks: in 2025 only 296 stocks (~15%) beat the market index; in 2021, 680 stocks (~40%); in 2022, 1,190 stocks (~68%). — [UDN, "2025年僅15%贏大盤"](https://udn.com/news/story/7251/9402539)
- **[TW][verified, journalistic — source data not stated]** A Business Today piece (Mar 2026) states roughly 80% of Taiwan individual stocks trail the index whether held 1 year or 20 years (still >70% at 20 years), with a strongly right-skewed return distribution. — [今周刊](https://www.businesstoday.com.tw/article/category/183012/post/202603050031/)
- **[US][verified]** Alpha Architect random-portfolio study (2015; random 15/50/100/300/500-stock draws monthly from the largest 1,000 US stocks): smaller portfolios have much wider return dispersion, and small random portfolios "lose more often than they win" against the equal-weighted index. — [Alpha Architect](https://alphaarchitect.com/how-many-stocks-should-you-own-the-costs-and-benefits-of-diversification/)
- **[US][verified, GROSS of costs, vendor with a commercial interest in concentrated funds]** Alpha Architect momentum construction study (1979-2015 backtest): a value-weighted, monthly-rebalanced 50-stock momentum portfolio earned 17.36% CAGR vs 10.89% for an annually rebalanced 500-stock momentum portfolio; "the fewer firms, the higher the CAGR, holding period constant". Their practical guide suggests 50-100 stocks as the balance point. — [Alpha Architect, portfolio construction and momentum funds](https://alphaarchitect.com/how-portfolio-construction-affects-momentum-funds/); [Alpha Architect guide](https://alphaarchitect.com/how-many-stocks-should-you-own-a-practical-guide-to-portfolio-construction/)

### Inferences
- **[own calc] Probability a random N-stock equal-weight draw from a momentum basket underperforms the market.** Model: basket has true alpha a = 1%/month; each stock has idiosyncratic (market-relative) monthly volatility s_i; the whole basket shares a common style/sector tracking error s_c that does NOT diversify. Then TE_N = sqrt(s_c^2 + s_i^2/N) and P(underperform over h months) ≈ Φ(−a·sqrt(h)/TE_N). (Normal approximation; i.i.d. months; ignores costs.)

  Case 1 — stock-specific noise only (s_c = 0), s_i = 10%/month (≈35% annualised, plausible for Taiwan mid/small momentum names):

  | N | TE/month | P(under) 1 month | P(under) 1 year | P(under) 3 years | months for t=2 | months for t=3 |
  |---|---|---|---|---|---|---|
  | 1 | 10.0% | 46% | 37% | 27% | 400 | 900 |
  | 5 | 4.47% | 41% | 22% | 9% | 80 | 180 |
  | 10 | 3.16% | 38% | 14% | 3% | 40 | 90 |
  | 20 | 2.24% | 33% | 6% | 0.4% | 20 | 45 |
  | 30 | 1.83% | 29% | 3% | 0.1% | 13 | 30 |

  Case 2 — realistic: add common momentum-style tracking error s_c = 3%/month (≈10% annualised, in line with the ~7.5-8.5% index-level tracking error of the diversified MSCI World Momentum index cited in A4, scaled up for a single small market), s_i = 10%:

  | N | TE/month | P(under) 1 month | P(under) 1 year | P(under) 3 years | months for t=2 | months for t=3 |
  |---|---|---|---|---|---|---|
  | 5 | 5.39% | 43% | 26% | 13% | 116 | 261 |
  | 10 | 4.36% | 41% | 21% | 8% | 76 | 171 |
  | 20 | 3.74% | 40% | 18% | 5% | 56 | 126 |
  | 30 | 3.51% | 39% | 16% | 4% | 49 | 111 |
  | 50 | 3.32% | 38% | 15% | 3.5% | 44 | 99 |

  With s_i = 12%: N=5 → 44% / 29% / 17%; N=10 → 42% / 24% / 11%; N=20 → 40% / 20% / 7%; N=30 → 39% / 18% / 5%.
- Reading the tables: (i) in any single month the coin is barely loaded (38-46% chance of losing to the market regardless of N) — monthly results carry almost no information; (ii) the marginal benefit of names flattens hard after ~20 because the common style risk dominates: going 20 → 50 only moves one-year underperformance from 18% to 15%; (iii) 5 → 10 → 20 are the valuable steps (26% → 21% → 18% one-year; 261 → 171 → 126 months to reach t=3).
- The 1 pp/month assumption is generous. If the true net edge is 0.5 pp/month, required sample length quadruples (months for t=2 with TE 3.74% = 224 months ≈ 19 years).
- Skewness correction: because most stocks lose to the index (Taiwan: only 15-40% of stocks beat the index in 2021/2025; ~20% over long horizons per the journalistic figure), the median outcome of a 5-stock pick is below its mean. The normal-approximation probabilities above are therefore optimistic for small N. This is the Bessembinder argument for owning more names: the basket's edge is delivered by a few outliers that a 5-stock draw will often miss.
- Practical conclusion for NT$300k-5M: target **15-25 names** (10 is a hard floor; below 10 the result is dominated by luck even over 3 years). At NT$300k and 20 names the slot is NT$15k, below one board lot for most stocks → odd lots are mandatory (see A3 for fee floors).

### Gaps
- No Bessembinder-style peer-reviewed study specific to Taiwan (share of TWSE/TPEx stocks beating the index or T-bills over lifetime) was found; Taiwan's row in the Bessembinder et al. 42-country table was not retrieved. The two Taiwan figures above are issuer/journalistic and unverified in method.
- Evans & Archer's original table and CLMX's exact "excess standard deviation at 20 vs 50 stocks" figures were not retrieved.
- No empirical (rather than modelled) estimate of the probability that N random picks from the top momentum quintile underperform the Taiwan index; this should be computed directly in the codebase by bootstrap (draw N names from each month's top-quintile list 10,000 times, record the fraction of draws below benchmark at 1/12/36 months).

---

## A2. Position sizing: equal weight vs inverse-volatility vs fixed-fractional "1R" vs Kelly

### Takeaway
The evidence favours simple weighting: optimised weights need absurdly long estimation windows to beat 1/N, and the documented benefit of volatility scaling in momentum is at the portfolio (exposure) level — cutting exposure when momentum's own volatility is high — rather than from clever per-stock weights. For a retail book, equal weight (or inverse-vol with caps) plus a cap on total open risk is adequate; Kelly-type sizing is unusable at full size because the edge estimate is too noisy.

### Cited Findings
- **[US][verified]** DeMiguel, Garlappi & Uppal (2009, RFS): across 14 optimisation models and 7 datasets, none consistently beat the 1/N rule on Sharpe ratio, certainty-equivalent return or turnover; with US-calibrated parameters the sample-based mean-variance strategy needs an estimation window of ~3,000 months for 25 assets and ~6,000 months for 50 assets to beat 1/N. — [RFS record](https://econpapers.repec.org/RePEc:oup:rfinst:v:22:y:2009:i:5:p:1915-1953); [LBS summary](https://london.edu/faculty-and-research/academic-research/o/optimal-versus-naive-diversification-how-inefficient-is-the-1n-portfolio-strategy-p7805)
- **[US][verified]** Daniel & Moskowitz ("Momentum Crashes", NBER w20439 / JFE 2016): momentum's worst episodes follow market declines when the market rebounds — Jul-Aug 1932 the past-loser decile returned 236% vs 30% for winners; Mar-May 2009 losers rose 163% vs 8% for winners. The crash is driven by the short (loser) leg. — [NBER w20439](https://www.nber.org/system/files/working_papers/w20439/w20439.pdf)
- **[US][verified, secondary]** Alpha Architect summary: long-short momentum lost ~91% Jun-Aug 1932 and >73% within three months in 2009; they characterise long-only momentum as not subject to crashes of that depth. — [Alpha Architect, Avoiding momentum crashes](https://alphaarchitect.com/avoiding-momentum-crashes/)
- **[US][verified]** Alpha Architect's reliability paper argues concentrated (≈50-stock) factor portfolios beat diluted factor portfolios more reliably — i.e. the choice of how many names and how pure the signal matters more than the weighting scheme. — [Alpha Architect](https://alphaarchitect.com/how-portfolio-construction-impacts-the-reliability-of-outcomes/)

### Inferences
- **Equal weight vs inverse-vol.** Inverse-vol weights w_i ∝ 1/σ_i (σ_i = 20-60-day realised vol or ATR%/price) equalise each position's risk contribution when correlations are similar. In a momentum basket, the highest-vol names are frequently the strongest recent winners, so inverse-vol systematically underweights the names carrying the signal; the expected effect is lower volatility and drawdown, with ambiguous effect on return. Treat it as a risk-control choice to be A/B-tested, not as an alpha source. Acceptance rule: the strategy must pass under BOTH equal weight and inverse-vol; if it only passes under one, the "edge" is a sizing artefact.
- **Fixed-fractional "1R".** Size = (equity × r) / (entry − stop). With r = 1% of equity and a stop 8% below entry, position = 12.5% of equity → at most 8 positions fully invested; with r = 0.5%, 6.25% each → 16 positions. So 1R sizing with the usual 1% risk is mathematically a *concentration* rule: it yields 6-10 names, which A1 shows is too few for a 1 pp/month edge to be visible. For a 15-25-name book use r ≈ 0.3-0.5% with stops of 7-10%, or simply equal weight with a cap (e.g. max 7% per name) and a stop. 1R sizing is equivalent to inverse-vol sizing when the stop distance is a multiple of ATR.
- **Kelly.** For a strategy with mean excess return μ and variance σ² per period, growth-optimal leverage f* = μ/σ². Fractional Kelly at c·f* earns a fraction c(2−c) of the maximum growth rate with c times the volatility: half-Kelly keeps 75% of growth with 50% of the volatility; over-betting at 2·f* gives zero growth. For discrete bets with win-probability p and payoff ratio b: f* = p − (1−p)/b. Example: p = 45%, average win/average loss b = 2.0 → f* = 0.45 − 0.55/2 = 17.5% of equity at risk per bet; half-Kelly 8.75%. But p and b are estimated with large error: with 100 trades the standard error of p is sqrt(0.45·0.55/100) ≈ 5 pp, so the 95% interval for f* runs from ~3% to ~32%. This estimation error is the reason for fractional Kelly (≤ 0.25-0.5×) and why Kelly is a ceiling check, not a sizing rule, for a retail swing book. (Standard results; no source fetched this session — see Gaps.)
- **Why sizing matters less than breadth and cost.** From the A1 tables, moving from 5 to 20 names cuts required validation time from 261 to 126 months; from A3, monthly full turnover costs ~8%/year vs ~2-3%/year with buffers. No plausible weighting tweak has an effect of that magnitude.

### Gaps
- Barroso & Santa-Clara (2015, "Momentum has its moments" — volatility-scaled momentum roughly doubles the Sharpe ratio) was searched but not retrieved; the commonly quoted 0.53 → 0.97 Sharpe improvement is **unverified this session** and applies to long-short US momentum, not long-only.
- No Taiwan-specific study comparing equal-weight vs inverse-vol momentum portfolios was found.
- No source was fetched for the Kelly/fractional-Kelly results (Kelly 1956; Thorp; MacLean-Thorp-Ziemba); the formulas above are textbook results that the writer may want to cite from a primary source.

---

## A3. Rebalance frequency, overlapping tranches, turnover buffers, and Taiwan cost drag

### Takeaway
The 0.3% sell-side transaction tax cannot be discounted and puts a hard floor of ~0.38-0.47% on every round trip before spread/slippage; fully turning the book over every month costs roughly 7-10% a year, which consumes most of a 1 pp/month gross edge. Rebalance monthly at most, stagger entries into tranches, and use a buy/hold buffer (buy top 10-20%, hold until a name falls out of the top 30-40%).

### Cited Findings
- **[TW][verified]** Brokerage commission statutory cap 0.1425% of trade value on both buy and sell; securities transaction tax 0.3% on sells of ordinary shares (0.1% for ETFs); broker discounts reduce the commission but never the tax. — [Money101, 2026 股票手續費](https://www.money101.com.tw/blog/%e8%b2%b7%e8%b3%a3%e8%82%a1%e7%a5%a8%e6%89%8b%e7%ba%8c%e8%b2%bb%e6%80%8e%e9%ba%bc%e7%ae%97%ef%bc%9f%e4%b8%80%e5%bc%b5%e5%9c%96%e8%a1%a8%e8%ae%93%e4%bd%a0%e4%b8%80%e7%9c%8b%e5%b0%b1%e6%87%82)
- **[TW][verified]** 2026 broker comparison: several brokers (e.g. 宏遠, 元富, 群益) list 65折 (35% off) electronic-order discounts with a NT$1 minimum fee on odd lots; "最低1元" means the fee is floored at NT$1 when the computed fee is below NT$1, not a flat NT$1 per order; actual discounts vary by promotion and monthly volume. — [Money101, 2026 零股手續費比較](https://www.money101.com.tw/blog/%e7%86%b1%e9%96%80%e5%88%b8%e5%95%86%e6%af%94%e4%b8%80%e6%af%94)
- **[TW][verified]** Intraday odd-lot trading (盤中零股) launched 26 Oct 2020; matching is by call auction, interval cut from 3 minutes to 1 minute on 19 Dec 2022. Odd-lot daily turnover averaged NT$1.876bn (0.56% of market value traded) through Jul 2022, and NT$2.968bn (~0.91%) from launch to Oct 2024. Odd lots cannot be day-traded. — [CNA](https://www.cna.com.tw/news/afe/202208150262.aspx); [工商時報 2024-11-26](https://www.ctee.com.tw/news/20241126700245-430201); [Money101 零股](https://www.money101.com.tw/blog/零股-交易時間-手續費-股票)
- **[TW][verified, sources conflict on date]** Intraday odd-lot first match is being moved from 09:10 to 09:00 to align with board-lot open: one article says the new regime starts 7 December; another quotes the TWSE chairman as "by end of 2026". Confirm against the TWSE/TPEx announcement. — [經理人](https://www.managertoday.com.tw/articles/view/59023); [Money101 零股](https://www.money101.com.tw/blog/零股-交易時間-手續費-股票)
- **[US][verified]** Novy-Marx & Velikov (2016, RFS, "A Taxonomy of Anomalies and Their Trading Costs"): a buy/hold spread (stricter threshold to enter than to stay) is the most effective cost-mitigation technique; most anomalies with <50% monthly turnover keep significant net spreads when designed to mitigate costs, few with higher turnover do. — [NBER w20721](https://www.nber.org/papers/w20721)
- **[US][verified, secondary — figure not checked against paper]** Momentum's trading cost is estimated at ~48 bp/month (1963-2013) in Novy-Marx-Velikov per an Alpha Architect summary; Frazzini, Israel & Moskowitz, using live AQR institutional executions, argue actual costs are less than a tenth of earlier estimates and that size/value/momentum survive costs (authors affiliated with AQR). The two differ mainly in cost measurement (effective-spread estimates vs realised institutional trades). — [Alpha Architect](https://alphaarchitect.com/2017/05/trading-costs-destroy-factor-investing/); [Alpha Architect on FIM](https://alphaarchitect.com/surprise-the-size-value-and-momentum-anomalies-survive-after-trading-costs/)
- **[US][verified, gross]** Alpha Architect: monthly-rebalanced 50-stock momentum 17.36% CAGR vs annually rebalanced 500-stock 10.89% (gross, 1979-2015) — faster rebalancing and concentration raise GROSS return; the article itself flags that costs are excluded. — [Alpha Architect](https://alphaarchitect.com/how-portfolio-construction-affects-momentum-funds/)
- **[Global][verified]** MSCI World Momentum index (semi-annual rebalance with conditional ad-hoc rebalances) reports one-way annual turnover of roughly 115% (Oct 2026 factsheet) to 154% (Aug 2025 factsheet). — [MSCI factsheet (verify URL maps to World Momentum)](https://www.msci.com/documents/10199/904e031c-94e4-4dbc-a314-7c373446dffa)

### Inferences
- **[own calc] Taiwan round-trip cost (buy + sell), % of notional** = 2 × 0.1425% × discount + 0.30% tax + slippage:

  | Commission discount | Fees + tax only | + 0.1% slippage | + 0.2% | + 0.4% | + 1.0% |
  |---|---|---|---|---|---|
  | none (0.1425%) | 0.585% | 0.685% | 0.785% | 0.985% | 1.585% |
  | 6折 | 0.471% | 0.571% | 0.671% | 0.871% | 1.471% |
  | 5折 | 0.443% | 0.543% | 0.643% | 0.843% | 1.443% |
  | 28折 | 0.380% | 0.480% | 0.580% | 0.780% | 1.380% |

  The tax is 64-79% of the fee+tax total; commission shopping saves at most ~0.2 pp per round trip.
- **[own calc] Annual cost drag = one-way annual turnover × round-trip cost.** At 0.67% per round trip (6折 + 0.2% slippage): 100%/month turnover (replace whole book monthly) → 12 × 0.67% ≈ **8.0%/yr**; 50%/month → 4.0%/yr; 25%/month (≈300%/yr) → 2.0%/yr; 115-154%/yr (MSCI-index-like) → 0.8-1.0%/yr. A weekly full-turnover system would pay ~35%/yr — not viable. A 1 pp/month gross edge (~12.7%/yr) leaves only ~4.7%/yr after full monthly turnover, vs ~10.7%/yr at 25%/month turnover.
- **[own calc] Minimum-fee trap.** Where a NT$20 minimum applies (common for board-lot orders; check the broker), the fee floor binds below NT$14,035 per order at the full rate and below NT$23,392 at 6折; a NT$5,000 order would pay 0.4% commission each way (round trip 1.1% incl. tax). With a NT$1 odd-lot minimum the floor binds only below ~NT$1,170 (6折). So for a NT$300k account with 20 slots of NT$15k, use a broker with a NT$1 odd-lot minimum, or the fee floor adds ~0.1 pp per round trip.
- **Odd-lot execution.** Odd lots trade in a separate book with 1-minute call auctions and only ~0.9% of market turnover; for mid/small caps the odd-lot book can be thin, so backtests for the NT$300k-1M tier should assume wider slippage (e.g. 0.3-0.5% per side for names outside the top ~150 by turnover, vs 0.1-0.2% for liquid large caps) and use limit orders. These slippage bands are my working assumptions, not measured values (see Gaps).
- **Overlapping tranches (Jegadeesh-Titman style).** Split capital into K tranches (K = 3-4), each rebalanced every K periods on staggered dates (e.g. 4 weekly tranches each held ~4 weeks, or 3 monthly tranches held 3 months). Effects: (a) removes rebalance-date luck — a single monthly rebalance date is one more hidden parameter; (b) holding period is K× longer so turnover is ~1/K of single-date rebalancing; (c) number of names rises naturally. Backtest acceptance should require the result to hold for every possible rebalance-day offset (e.g. all 20 trading-day offsets), with the spread between best and worst offset reported.
- **Buy/hold buffer rule (Novy-Marx-Velikov applied).** Enter only from the top decile/quintile; exit only when a holding drops below the top 30-40% (or hits its stop). Expect this to cut turnover by roughly half vs strict top-quintile membership while retaining most of the gross premium; verify in the backtest by reporting gross return, turnover and net return for buffer vs no-buffer.
- **Liquidity filter.** For NT$5M with 20 slots (NT$250k each), limiting each order to ≤1% of the stock's 20-day average daily value traded requires ADV ≥ NT$25M; at NT$300k (NT$15k slots) capacity is not binding, but the spread/price-limit risk of illiquid names still is. Suggested universe filter: 20-day median daily value ≥ NT$20-50M and price ≥ NT$10. (Working rule, not sourced.)

### Gaps
- No measured data on odd-lot (盤中零股) effective bid-ask spreads by liquidity tier was found; the slippage bands above are assumptions and should be calibrated with a few weeks of the user's own fills.
- The exact Novy-Marx-Velikov figure for net momentum return under a 10%/20% (or 20%/80%) buy/hold rule was not retrieved.
- Jegadeesh & Titman (1993) was not fetched; the tranche construction described is the standard overlapping-portfolio method from that paper but no numbers are cited from it.
- Broker minimum-fee policies (NT$20 vs NT$1) change with promotions; verify with the actual broker.

---

## A4. Realistic expectations: excess return, tracking error, drawdown, and how long momentum can lag

### Takeaway
The best-documented diversified long-only momentum index earned ~2.8 pp/yr over its parent (gross, before any costs) with ~7.5-8% tracking error — an information ratio of ~0.35-0.4 — and a 55% maximum drawdown, no better than the market's. At that IR, a genuine momentum edge still has a ~25% chance of trailing the index over 3 years and ~10-19% over 10 years. Taiwan evidence is weaker still: classic academic price momentum has historically been insignificant in Taiwan, and since 2024 any portfolio underweight TSMC has faced a severe benchmark headwind against 0050.

### Cited Findings
- **[Global][verified]** MSCI World Momentum index (USD, gross returns, no transaction costs): 11.54% annualised vs 8.72% for MSCI World from 30 Jun 1994 to 29 Aug 2025 (+2.82 pp/yr); 10-year 13.99% vs 12.22%; tracking error ~7.5-8.0% since 1994; maximum drawdown ~55.5-55.8% (29 Oct 2007 - 9 Mar 2009); turnover 115-154%. An older MSCI presentation (May 1973 - May 2018) gives tracking error 8.49% and information ratio 0.33. — [MSCI World Momentum factsheet (verify URL)](https://www.msci.com/documents/10199/904e031c-94e4-4dbc-a314-7c373446dffa); [MSCI doc 2](https://www.msci.com/documents/10199/024576f2-f48e-4efd-bdf5-3b9ebe4a19e7)
- **[TW][verified]** Chui, Titman & Wei (2010, J. Finance) link momentum profits to cultural individualism; Taiwan (low Hofstede individualism) is cited as a market where momentum profits are insignificant, whereas they are significant in the US. — [J. Finance record](https://econpapers.repec.org/RePEc:bla:jfinan:v:65:y:2010:i:1:p:361-392); [HKUST summary](https://bm.hkust.edu.hk/bizinsight/2010/05/roll-cross-cultural-differences-momentum-profits)
- **[TW][verified]** Du, Huang & Liao (2009, J. Economics & Business), "Why is there no momentum in the Taiwan stock market?": momentum strategies usually do not produce significant profits in emerging markets including Taiwan; momentum profits are more negative following DOWN markets in Taiwan than in the US. — [IDEAS](https://ideas.repec.org/a/eee/jebusi/v61y2009i2p140-152.html)
- **[TW][verified, working paper]** Sun, Tsai & Wang (2011, MPRA): in Taiwan, momentum works only at formation/holding periods longer than six months, yields significantly positive returns in up markets and negative-but-insignificant returns in down markets; institutional over-confidence drives up-market momentum. — [MPRA 37281](https://mpra.ub.uni-muenchen.de/37281/1/MPRA_paper_37281.pdf)
- **[TW][verified, journalistic]** 00733 (富邦臺灣中小A級動能50, small/mid-cap momentum ETF): a 2023 article states it beat the broad market in every full calendar year from 2019 and returned 243.44% in total over roughly 5.5 years since listing; another commentary describes its record as alternating flat stretches and very strong stretches. — [UDN 2023](https://udn.com/news/story/123006/7658787); [TWSE ETF page for 00733](https://www.twse.com.tw/zh/ETFortune/etfInfo/00733)
- **[TW][verified, journalistic, period not clearly stated]** A June 2026 ranking lists total returns of 75.89% for 00905 (FT臺灣Smart) and 75.52% for 00850 (元大臺灣ESG永續) vs 71.83% for 0050 over the same (unspecified) window. — [今周刊 2026-06-24](https://www.businesstoday.com.tw/article/category/183013/post/202606240019/)
- **[TW][verified, journalistic]** As of May 2026, TSMC is ~61% of 0050, vs ~30% in capped products such as 00850. A March 2026 article notes a momentum-type ETF excluding TSMC (009802) "clearly lagged" since listing because TSMC led the market over the prior year. — [今周刊 2026-05-05](https://www.businesstoday.com.tw/article/category/183013/post/202605050002/); [今周刊 2026-03-12](https://www.businesstoday.com.tw/article/category/183013/post/202603120041/)
- **[US][verified]** Long-short momentum suffers rare, extreme crashes after market panics (1932, 2009), concentrated in the short leg; see A2. — [NBER w20439](https://www.nber.org/system/files/working_papers/w20439/w20439.pdf)

### Inferences
- **[own calc] What an information ratio implies.** P(underperform benchmark over Y years) ≈ Φ(−IR·sqrt(Y)); years needed for t-stat k: Y = (k/IR)².

  | IR (annual) | P(lag) 1y | 3y | 5y | 10y | years for t=2 | years for t=3 |
  |---|---|---|---|---|---|---|
  | 0.30 | 38% | 30% | 25% | 17% | 44 | 100 |
  | 0.40 | 35% | 24% | 19% | 10% | 25 | 56 |
  | 0.50 | 31% | 19% | 13% | 6% | 16 | 36 |
  | 0.75 | 23% | 10% | 5% | 1% | 7.1 | 16 |
  | 1.00 | 16% | 4% | 1% | 0.1% | 4 | 9 |

  A diversified index-style momentum tilt has IR ≈ 0.35-0.4 gross. A retail book claiming IR ≥ 1 net should be presumed overfit until proven otherwise.
- **Expected numbers for a 15-25-stock Taiwan long-only momentum book (my synthesis, to be used as priors, not promises):** net excess return over 0050 total return 0-4 pp/yr; tracking error 10-15%/yr (higher than index products because of concentration and because 0050 is ~60% TSMC); IR 0-0.35; maximum drawdown at least as large as the index's (plan for −40% to −55%; MSCI World Momentum's −55.5% in 2007-09 was slightly worse than typical cap-weighted global indices); calendar-year hit rate vs 0050 ≈ 55-62% (from Φ(IR) with IR 0.15-0.3); underperformance stretches of 3-5 years are normal even with a real edge (19-30% probability at IR 0.3-0.4).
- **Benchmark problem specific to 2024-2026.** With TSMC ~61% of 0050, any 20-name equal-weight book holds ≤5% TSMC, so its tracking error vs 0050 is dominated by a single stock, not by the momentum signal. A backtest should report results against (a) 0050 total return, (b) an equal-weight universe benchmark, and (c) 0050 ex-TSMC proxy or the TAIEX total-return index (發行量加權股價報酬指數), otherwise "edge" and "TSMC underweight" are confounded.
- **Reconciling Taiwan academic evidence with ETF live records.** The pre-2010 literature (samples mostly 1980s-2000s) finds no significant cross-sectional price momentum in Taiwan, especially after down markets; 00733's 2019-2023 success is a short, bull-dominated, small/mid-cap sample. The honest prior is that Taiwan momentum is regime-dependent (works in up markets, fails after declines) — which is exactly the pattern a 2019-2026 backtest cannot test adequately.

### Gaps
- **MSCI Taiwan Momentum / MSCI Emerging Markets Momentum factsheets were not found** in search; no long-run Taiwan momentum index figures are reported here.
- **No same-period, annualised, total-return comparison of 00733 / 00905 / 00850 vs 0050 was found**; the figures above come from press articles with differing or unstated windows. These should be computed directly from adjusted NAV/price data (all four tickers are on Yahoo Finance) rather than cited.
- Longest historical stretch of long-only momentum underperformance vs the cap-weighted market (in years) was not found in any fetched source; AQR's "Fact, Fiction and Momentum Investing" was located but its drawdown detail was not retrieved. The probabilities in the IR table are the substitute.
- Post-2015 peer-reviewed evidence on Taiwan momentum (after the ±10% price limit took effect) was indicated to exist (2016-2023 papers) but not retrieved.

---

## A5. Retail trader performance in Taiwan — calibrating "confidence"

### Takeaway
The base rate is poor: Taiwan individual investors in aggregate lose 3.8 pp/yr to trading, nearly two-thirds of it from costs, and fewer than 1% of day traders are reliably profitable after fees. A retail rule should be presumed unprofitable until it clears a pre-set evidence bar; the realistic meaning of "confident" is "passed a pre-registered test whose false-positive rate is known", not "certain to make money".

### Cited Findings
- **[TW][verified]** Barber, Lee, Liu & Odean (2009, RFS; all trades by all investors on TWSE, 1995-1999): the aggregate portfolio of individuals suffers an annual performance penalty of 3.8 percentage points; individual losses equal 2.2% of Taiwan's GDP or 2.8% of total personal income; "virtually all individual trading losses can be traced to their aggressive orders"; institutions gain. — [Haas PDF](https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/justhowmuchdoindividualinvestorslose_rfs_2009.pdf); [RFS record](https://econpapers.repec.org/RePEc:oup:rfinst:v:22:y:2009:i:2:p:609-632)
- **[TW][verified, press quote of author]** Slightly less than two-thirds of Taiwanese individual investors' losses stem from transaction costs (commissions and transaction tax), the rest from trading losses/market timing. — [Haas newsroom](https://newsroom.haas.berkeley.edu/individual-investors-see-red-prof-terry-odean-finds/)
- **[TW][verified — abstract quoted]** Barber, Lee, Liu & Odean (2014, J. Financial Markets; all Taiwan day traders 1992-2006): sorting on year-y returns, the 500 top-ranked day traders earn 61.3 bp/day before fees (37.9 bp after fees) in year y+1; bottom-ranked traders earn −11.5 bp (−28.9 bp after fees); "Less than 1% of the day trader population is able to predictably and reliably earn positive abnormal returns net of fees." — [J. Financial Markets record](https://econpapers.repec.org/RePEc:eee:finmar:v:18:y:2014:i:c:p:1-24)
- **[TW][verified, working paper]** A companion paper on learning among Taiwan day traders (1992-2006) concludes most speculators lose money and that rational-learning models cannot explain much of the persistence of speculative trading (unprofitable traders keep trading). — [Haas working paper](https://faculty.haas.berkeley.edu/odean/papers/day%20traders/day%20trading%20and%20learning%20110217.pdf)

### Inferences
- Behaviours that drive the losses, per these papers: high turnover (costs are ~2/3 of the loss), aggressive (marketable) orders, and persistence despite losses. Direct design implications: cap turnover (A3), use limit orders / next-open or close auction rather than chasing intraday, and adopt a written kill rule.
- These samples are 1992-2006, when the transaction tax and commission structure were similar (0.3% tax) but before online discounts, intraday odd lots, and the 2017 day-trading tax halving; the direction of the result is unlikely to have reversed but the magnitude today is unknown.
- Calibration: skill persistence exists (top 500 day traders) but is extremely rare. A swing trader's prior probability of having a real edge should be set low (a few percent to perhaps 10-20% for a low-turnover, academically grounded factor rule), which is precisely why the multiple-testing hurdles in B2 (t ≥ 3, deflated Sharpe) are appropriate rather than the conventional t ≥ 2: by Bayes, with a 10% prior and 80% power, a p<0.05 result is a false positive ~36% of the time (0.9×0.05 / (0.9×0.05 + 0.1×0.8)); at p<0.003 (t≈3) it is ~3%.

### Gaps
- No post-2015 peer-reviewed estimate of the fraction of Taiwan retail swing (multi-day/multi-week) traders who are profitable net of costs was found; the cited evidence is aggregate (all individuals) or day-trader-specific.
- The earlier working-paper versions of the day-trading paper report different skill fractions (one snippet mentioned ~15% of day traders earning abnormal returns before costs in some sorts); only the published abstract's "<1%" was verified.

---

## B1. Survivorship bias with currently-listed-only data; delisting returns; Taiwan delisting counts and free data

### Takeaway
TWSE's own list shows 266 main-board delistings since 2001 — roughly 7-13 a year in 2011-2022 and 2-5 a year in 2023-2026 — so a 10-15-year backtest on today's ~1,000 TWSE names silently drops on the order of 90-120 TWSE companies (plus TPEx delistings, not counted here). The bias is asymmetric: it flatters dip-buying/reversal rules most (the losers that never bounced are missing), but it also flatters breakout/momentum rules by removing failed breakouts in names that later collapsed, and it inflates the universe's average return (making the equal-weight benchmark look better too). A free delisting list exists; free delisted price history largely does not.

### Cited Findings
- **[TW][verified — table fetched and counted 22 Nov 2026]** TWSE "終止上市公司" table: 266 rows, from ROC 90 (20 Jan 2001) to ROC 115 (18 Nov 2026); columns are delisting date, company name, stock code. Counts by year: 2001: 16; 2002: 31; 2003: 14; 2004: 10; 2005: 19; 2006: 14; 2007: 20; 2008: 12; 2009: 3; 2010: 12; 2011: 8; 2012: 6; 2013: 7; 2014: 7; 2015: 8; 2016: 10; 2017: 8; 2018: 10; 2019: 8; 2020: 7; 2021: 10; 2022: 13; 2023: 2; 2024: 3; 2025: 3; 2026 (to 18 Nov): 5. Sum 2012-2026 = 107; sum 2016-2026 = 79. The page offers CSV and HTML output. — [TWSE 終止上市公司](https://www.twse.com.tw/company/suspendListingCsvAndHtml?lang=zh&type=html)
- **[TW][verified]** TWSE annual statistics count delistings slightly differently by year (some include TDRs, foreign primary listings, or board transfers): 2019: 8 (4 domestic, 1 foreign primary, 3 TDR); 2020: 7; 2022: 13 (7 domestic, 5 foreign primary, 1 TDR; one was a conversion to a holding company — 定穎 → 定穎投控); 2023: 2; 2024: 2; 2025: 2. Recent individual delistings include 三商壽 (2867, 1 Sep 2026), 森崴能源 (6806, 23 Jun 2026), 晶睿 (3454, 27 Mar 2026). — [TWSE annual 2022 P4](https://www.twse.com.tw/downloads/en/about/company/annual/2022/P4.pdf); [TWSE annual 2023 P4](https://www.twse.com.tw/downloads/en/about/company/annual/2023/P4.pdf); [TWSE 年報 114 P4](https://www.twse.com.tw/downloads/zh/about/company/Annual/114/P4.pdf)
- **[US][verified]** Shumway (1997, J. Finance, "The Delisting Bias in CRSP Data"): correct delisting returns are missing for most stocks delisted for negative (performance) reasons since 1962, which biases portfolio returns upward. — [IDEAS](https://ideas.repec.org/a/bla/jfinan/v52y1997i1p327-40.html)
- **[US][recalled — not seen in a fetched source this session]** Shumway (1997) estimates the missing delisting return for performance-related NYSE/AMEX delistings at about −30%. — [IDEAS (same paper)](https://ideas.repec.org/a/bla/jfinan/v52y1997i1p327-40.html)
- **[US][verified]** Shumway & Warther (1999, J. Finance): for Nasdaq, using a corrected return of −55% for missing performance-related delisting returns removes the bias; after the correction "there is no evidence that there ever was a size effect on Nasdaq" — i.e. an entire published anomaly was an artefact of missing delisting returns. — [IDEAS](https://ideas.repec.org/a/bla/jfinan/v54y1999i6p2361-2379.html)

### Inferences
- **Not every delisting is a wipe-out.** The TWSE list mixes mergers/acquisitions/privatisations/holding-company conversions (often at a premium — e.g. 定穎, and tender-offer cases) with failures (全額交割 → 下市, negative net worth, failure to file financials). The list has no "reason" column in the fetched view, so each code must be classified (the MOPS announcements / press give the reason). Only performance delistings warrant a −30% to −100% terminal return.
- **Rough size of the bias (own estimate, to be replaced by measurement).** If ~8 TWSE names/yr delist out of ~950-1,050 listed (~0.8%/yr), and perhaps one-third to one-half are distress cases with terminal losses of −50% to −100% over their last year, the equal-weight universe return is overstated by roughly 0.15-0.4 pp/yr — small for the universe average. But the effect on a *selected* portfolio can be several times larger because distress candidates are not randomly distributed: they cluster among small, low-priced, high-volatility names, which is exactly where breakout scanners find many signals. For reversal/"buy the 52-week-low" rules the bias can be decisive. Adding TPEx (櫃買) delistings, which were not counted here, would raise all of these numbers.
- **Direction by strategy type.** Momentum long-only: survivorship removes names that broke out then collapsed (fraud/accounting blow-ups) → modest upward bias in win rate and average return; also removes winners that were acquired at a premium → small offsetting downward bias. Reversal / deep-value / low-price rules: strong upward bias. Any rule with a "price < NT$10" or "new low" component should be considered invalid on survivor-only data.
- **Yahoo Finance specifics.** yfinance generally returns no history for delisted .TW/.TWO tickers, so a "currently listed" download is survivor-only by construction; also, the *current* constituent list applied to past dates is a look-ahead (stocks that IPO'd in 2022 obviously did not exist in 2015, but more subtly, today's list excludes all the failures). Minimum mitigation with free data: (1) download the TWSE 終止上市 CSV and the TPEx equivalent; (2) for each backtest year report how many then-listed names are missing from the dataset; (3) run a **stress test**: for each delisted code, if the strategy's rules would plausibly have held it (cannot be known without prices), inject synthetic terminal losses — e.g. randomly assign k% of open positions per year (k = the historical distress-delisting rate × a concentration multiplier of 2-3) a −50%/−100% outcome — and require the strategy to still pass; (4) where possible fetch delisted price history from the TWSE daily quotes archive (個股日成交資訊 / 每日收盤行情, queryable by date so delisted codes appear on the dates they traded) and FinMind's free tier.

### Gaps
- TPEx (上櫃) delisting counts and the URL of the TPEx 終止上櫃 list were not retrieved; TPEx delistings are likely as numerous as TWSE's or more.
- No published estimate of survivorship-bias magnitude for Taiwan strategy backtests, and no source quantifying the bias specifically for momentum vs reversal, was found; the figures in Inferences are my rough arithmetic.
- Whether FinMind / TWSE open-data archives provide complete adjusted histories for delisted codes was not verified this session.
- The TWSE list gives no delisting reason; the split between M&A and distress delistings is unknown.

---

## B2. Multiple testing and data snooping: thresholds and formulas

### Takeaway
The conventional t > 2 is not evidence once more than a handful of variants have been tried. Use t ≥ 3 as the default hurdle for a new rule, scale the hurdle with the number of variants tried (Bonferroni: t ≈ 2.8 for 10 trials, 3.0 for 20, 3.3 for 50, 3.5 for 100), require the Sharpe ratio to exceed the expected maximum Sharpe of that many zero-skill trials (for 10 years of monthly data: ~0.5 for 10 trials, ~0.8 for 100, ~1.0 for 1,000), and expect live performance to be roughly half the backtest.

### Cited Findings
- **[US][verified]** Harvey, Liu & Zhu (2016, RFS; NBER w20592): after accounting for the hundreds of factors tried in the literature, "a newly discovered factor needs to clear a much higher hurdle, with a t-ratio greater than 3.0"; they catalogue at least 316 tested factors. — [NBER w20592](https://www.nber.org/papers/w20592.pdf)
- **[US][verified — full text read]** Harvey & Liu (2015, J. Portfolio Management, "Backtesting"): the customary 50% Sharpe-ratio haircut is "only a rule of thumb"; the correct multiple-testing haircut is nonlinear — "the highest Sharpe ratios are only moderately penalized, while the marginal Sharpe ratios are heavily penalized". Method: convert Sharpe to t-stat via t = SR_annual × sqrt(T_months/12) (equivalently SR × sqrt(years)), get the single-test p-value, adjust it for M tests (Bonferroni: p_M = min(M·p, 1); Holm and BHY are less severe step procedures), convert the adjusted p-value back to a t-stat and a "haircut Sharpe ratio". Reported results: with 50 trials the haircut is almost 50% for the weakest example (E/P, SR 0.43) but only 7.9% for the strongest (BAB, SR 0.78); across methods, when annualised SR < 0.4 the haircut is almost always more than 50%, when SR > 1.0 it is at most 25%. Worked example: SR 1.0 over 120 months, monthly autocorrelation 0.1, 100 tests, average correlation 0.4 among strategies → autocorrelation-corrected SR 0.912 → BHY-adjusted SR 0.438 (haircut 52.0%). — [Harvey & Liu, Backtesting (Duke PDF)](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)
- **[US][verified]** Harvey & Liu also suggest combining in-sample/out-of-sample with multiple testing: run in-sample with a lenient cutoff (e.g. p = 0.2), check OOS survival, run the multiple-testing adjustment on the full sample, and keep only the intersection of survivors. — [Harvey & Liu, Backtesting](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)
- **[US][verified — full text read]** False Strategy Theorem (López de Prado & Bailey, American Mathematical Monthly 2021; basis of the Deflated Sharpe Ratio, Bailey & López de Prado 2014 JPM): among K independent trials whose true Sharpe ratio is zero, the expected maximum estimated Sharpe ratio is strictly positive and rises with K; with K = 1,000 trials and unit variance of the SR estimates the expected maximum is 3.26. Example: a Sharpe of 2.5 on 5 years of daily data is significant at 0.9999 confidence after one trial, but confidence drops below 0.95 after only 89 independent trials. The expected maximum is "the hurdle that the reported Sharpe ratio must exceed". Approximation: E[max_k SR_k] ≈ sqrt(V[SR_k]) × ((1 − γ)·Z⁻¹[1 − 1/K] + γ·Z⁻¹[1 − 1/(K·e)]), γ = 0.5772 (Euler-Mascheroni), Z⁻¹ = inverse standard normal CDF. — [False Strategy Theorem, eScholarship](https://escholarship.org/uc/item/95t7k79q); [Deflated Sharpe Ratio, SSRN 2460551](https://papers.ssrn.com/abstract=2460551)
- **[verified, secondary]** Trials are rarely independent; López de Prado (2018) proposes estimating the *effective* number of independent trials by clustering similar strategies' return series (e.g. hierarchical clustering). — [Wikipedia: Deflated Sharpe ratio (as summarised in search)](https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio)
- **[verified, bibliographic only]** Probability of Backtest Overfitting (Bailey, Borwein, López de Prado & Zhu, J. Computational Finance 2017) via combinatorially symmetric cross-validation (CSCV). — [eScholarship PDF](https://escholarship.org/content/qt2329p290/qt2329p290.pdf)
- **[US][verified in part]** McLean & Pontiff (2016, J. Finance; 97 predictors): return predictability declines both out-of-sample and post-publication but does not disappear. The **published** abstract's widely quoted figures are 26% lower out-of-sample and 58% lower post-publication, implying a ~32% publication-informed-trading effect — this session's search confirmed the 97 predictors and the ~32% figure but not the 26%/58% text directly **[recalled]**. An **earlier working-paper version (fetched and read)** reports ~10% out-of-sample decay and ~35% post-publication decay ("an in-sample alpha of 5% is expected to decay to 3.25% post-publication"), and in one specification average returns at 78% of in-sample during the out-of-sample-pre-publication period and 51% post-publication. — [J. Finance record](https://econpapers.repec.org/RePEc:bla:jfinan:v:71:y:2016:i:1:p:5-32); [working-paper PDF](https://ivey.uwo.ca/media/3775549/pontiff.pdf)
- **[US][verified]** Hou, Xue & Zhang (2020, RFS, "Replicating Anomalies"; NBER w23394): with NYSE breakpoints and value-weighted returns (to limit microcap influence), 286 of 447 anomalies (64%) are insignificant at the 5% level; with a t ≥ 3 cutoff, 380 (85%) fail. Within original-sample periods 65.4% cannot clear |t| ≥ 1.96. — [NBER w23394](https://www.nber.org/papers/w23394.pdf)
- **[US][verified — dissenting view]** Later replication work disputes the severity: one study reproduces predictability for essentially 100% of the characteristics in the HXZ sample using original methods, and another estimates the false-discovery rate among published predictors at ~1.5%, arguing the 1.96 hurdle need not be raised — the disagreement is largely about microcaps/equal- vs value-weighting. — [arXiv 2209.13623](https://arxiv.org/pdf/2209.13623); [Federal Reserve FEDS 2021-037](https://www.federalreserve.gov/econres/feds/files/2021-037pap.pdf)

### Inferences
- **Deflated Sharpe Ratio formulas [recalled from Bailey & López de Prado 2014; the E[max] formula above is verified, the PSR/DSR/MinTRL expressions below are from memory and should be checked against the SSRN paper before coding]:**
  - Probabilistic Sharpe Ratio: PSR(SR*) = Φ( (SR̂ − SR*)·sqrt(T − 1) / sqrt(1 − γ₃·SR̂ + ((γ₄ − 1)/4)·SR̂²) ), where SR̂ is the per-period (non-annualised) Sharpe, T the number of return observations, γ₃ skewness, γ₄ kurtosis (3 for normal).
  - Deflated Sharpe Ratio: DSR = PSR(SR₀) with SR₀ = sqrt(V[SR̂_n]) × ((1 − γ)·Φ⁻¹[1 − 1/N] + γ·Φ⁻¹[1 − 1/(N·e)]), N = (effective) number of trials, V[SR̂_n] = cross-trial variance of the per-period Sharpe estimates. Accept if DSR ≥ 0.95.
  - Minimum Track Record Length: MinTRL = 1 + [1 − γ₃·SR̂ + ((γ₄ − 1)/4)·SR̂²] × (z_α / (SR̂ − SR*))².
  - Negative skew and fat tails (typical for breakout/momentum equity curves with gap-down losses) inflate the denominator → lower PSR for the same Sharpe.
- **[own calc] Expected maximum Sharpe of N zero-skill trials** (formula above; under the null the standard deviation of an annualised Sharpe estimate from T months is ≈ sqrt(12/T)):

  | N trials | E[max z] | Annual SR hurdle, 5 yrs data | 10 yrs | 15 yrs |
  |---|---|---|---|---|
  | 5 | 1.19 | 0.53 | 0.38 | 0.31 |
  | 10 | 1.58 | 0.70 | 0.50 | 0.41 |
  | 20 | 1.90 | 0.85 | 0.60 | 0.49 |
  | 50 | 2.28 | 1.02 | 0.72 | 0.59 |
  | 100 | 2.53 | 1.13 | 0.80 | 0.65 |
  | 500 | 3.05 | 1.37 | 0.97 | 0.79 |
  | 1,000 | 3.26 | 1.46 | 1.03 | 0.84 |

  Interpretation: a parameter grid of 100 variants on 10 years of data will, on average, throw up a best variant with Sharpe (of excess return vs benchmark) ≈ 0.8 when nothing works. Since a real long-only momentum IR is ~0.35-0.4 (A4), **a grid search over 100+ variants on 10 years of data cannot distinguish a real edge from noise by picking the best variant** — the best variant's Sharpe is expected to exceed the true signal's regardless.
- **[own calc] Bonferroni t-hurdles** (two-sided 5% family-wise): M=1: 1.96; 5: 2.58; 10: 2.81; 20: 3.02; 50: 3.29; 100: 3.48; 300: 3.76. "t > 3" corresponds to roughly 20 independent tries — a realistic count for one person's rule development (lookback × threshold × stop × filter choices usually exceeds this quickly).
- **Counting trials honestly.** Every configuration ever run against the evaluation data counts, including abandoned ideas, plus (partially) every idea borrowed from books/blogs that were themselves mined. Keep an append-only trial log in the repo (config hash, date, period, metrics). Use N = number of logged configs; optionally reduce to an effective N via clustering of return series.
- **White's Reality Check / Hansen's SPA (described from general knowledge, no source fetched):** bootstrap test of H0 "the best of M rules has no superior performance over the benchmark". Procedure: for each rule k compute the period-by-period excess return over benchmark d_k,t; statistic V = max_k sqrt(T)·mean(d_k); resample time indices with a stationary/block bootstrap (same indices for all rules, preserving cross-rule dependence) B ≥ 1,000 times, recentre each rule's mean, recompute the max; p-value = share of bootstrap maxima ≥ V. Hansen's SPA studentises each d_k and discards clearly inferior rules so that adding junk rules does not destroy power. This is the right test when the whole grid's return series are stored: it directly answers "is the best variant better than chance given that I searched M variants?"
- **Practical haircut rule for expectations.** Combining Harvey-Liu (SR < 0.4 → haircut > 50%; SR > 1 → ≤ 25%) with McLean-Pontiff (published anomalies lose 35-58% post-publication, and those survived peer review): plan on live excess return ≈ 40-50% of the backtest figure, and require the strategy to remain worthwhile after that haircut AND after costs.

### Gaps
- The DSR paper's SSRN page returned HTTP 403 and the PSR/DSR/MinTRL expressions were not re-read; only the expected-maximum formula and numerical examples were verified via the False Strategy Theorem paper.
- White (2000) and Hansen (2005) were not fetched; the description is from general knowledge without a citation.
- The CSCV/PBO procedure details were not retrieved (procedure in brief, from memory: split the T×N matrix of trial returns into S blocks; for every combination of S/2 blocks as in-sample, find the best in-sample trial and record its out-of-sample rank; PBO = fraction of combinations in which the in-sample winner ranks below the OOS median; PBO < 0.05-0.10 is a commonly used acceptance level — unverified).
- McLean-Pontiff's published 26%/58% figures were not directly seen this session (working-paper version shows 10%/35%).

---

## B3. Sample size: how many months / trades are needed

### Takeaway
t = (mean / standard deviation) × sqrt(n), so n = (t × σ / μ)². A 1%/month excess return with 4%/month tracking error needs 64 months for t = 2 and 144 months (12 years) for t = 3; halve the edge and the requirement quadruples. Per-trade statistics are only valid if trades are independent — overlapping, same-day, same-sector trades are not, so count independent time blocks, not trades.

### Cited Findings
- **[US][verified]** The relation between Sharpe ratio and t-statistic used by Harvey & Liu: t = SR_annual × sqrt(T/12) with T in months (their Exhibit 1), i.e. a strategy's t-stat is its annual Sharpe times the square root of the number of years. Their program also corrects the Sharpe ratio for return autocorrelation (example: SR 1.0 with monthly autocorrelation 0.1 → corrected SR 0.912). — [Harvey & Liu, Backtesting](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)
- **[US][verified]** Purging and embargoing exist precisely because overlapping multi-day labels share information, so adjacent observations are not independent. — [Wikipedia: Purged cross-validation](https://en.wikipedia.org/wiki/Purged_cross-validation)

### Inferences
- **[own calc] Months required, n = (t·σ/μ)²** (μ = monthly mean excess return over benchmark, σ = monthly tracking error; i.i.d. months):

  | μ / month | σ / month | annual IR | n for t=2 | n for t=3 | n for 80% power at 5% two-sided ((1.96+0.84)·σ/μ)² |
  |---|---|---|---|---|---|
  | 1.0% | 4% | 0.87 | 64 (5.3 y) | 144 (12 y) | 125 (10.5 y) |
  | 1.0% | 3% | 1.15 | 36 (3 y) | 81 (6.8 y) | 71 |
  | 1.0% | 5% | 0.69 | 100 (8.3 y) | 225 (18.8 y) | 196 |
  | 0.5% | 4% | 0.43 | 256 (21 y) | 576 (48 y) | 502 |
  | 0.5% | 3% | 0.58 | 144 (12 y) | 324 (27 y) | 282 |
  | 0.3% | 3% | 0.35 | 400 (33 y) | 900 (75 y) | 784 |

  Note the difference between "t=2 given the realised mean equals the true mean" (64 months) and having an 80% chance of detecting the edge (125 months): with only 64 months the test has ~50% power.
  Consequence: with ~10-15 years of free Yahoo data (120-180 months), only edges with IR ≳ 0.8-0.9 can reach t = 3. A realistic momentum IR of 0.35-0.5 is **not statistically provable** on Taiwan data alone in that window — the backtest can at best fail to contradict it. This is why priors from out-of-sample evidence in other markets/periods and economic rationale must carry part of the weight.
- **[own calc] Per-trade version.** n = (t·s/m)², m = mean net return per trade, s = standard deviation per trade. Swing trades with m = +1.5%, s = 12% → 256 trades for t = 2, 576 for t = 3; m = +1.0%, s = 10% → 400 / 900; m = +2%, s = 10% → 100 / 225. In win-rate terms with payoff ratio b: expectancy per unit risk E = p·b − (1 − p); with p = 40%, b = 2 → E = +0.2R, per-trade SD ≈ 1.47R → n for t = 2: 216 trades, for t = 3: 486.
- **Independence correction.** Trades opened in the same week in correlated stocks are close to one observation. Effective sample size n_eff ≈ n / (1 + (m̄ − 1)·ρ̄), where m̄ = average number of concurrently open positions and ρ̄ their average pairwise correlation of trade P&L. With 15 concurrent positions and ρ̄ = 0.3, n_eff ≈ n/5.2: 500 trades ≈ 96 independent observations. Safer practice: aggregate to portfolio-level weekly or monthly returns and test those.
- **Overlapping returns.** If the statistic uses h-period overlapping returns (e.g. 20-day forward returns sampled daily), the naive t-stat is overstated by up to ≈ sqrt(h). Remedies: (a) non-overlapping sampling (lose data but valid); (b) Newey-West HAC standard errors with lag ≥ h − 1 (Bartlett weights w_j = 1 − j/(L+1); variance = γ₀ + 2·Σ_{j=1..L} w_j·γ_j; rule-of-thumb lag when no overlap is known: L = floor(4·(T/100)^(2/9))); (c) Hansen-Hodrick (uniform weights, lag h − 1; can be non-positive-definite in small samples); (d) for a serially correlated portfolio return with first-order autocorrelation ρ, t-stat inflation ≈ sqrt((1+ρ)/(1−ρ)) → 10% at ρ = 0.1. (Standard econometrics; no source fetched.)
- **Block bootstrap for confidence intervals.** Resample the portfolio's excess-return series in blocks to preserve autocorrelation and volatility clustering: stationary bootstrap (Politis-Romano) with mean block length ≈ 1-3 months for monthly decisions (≈ 20-60 trading days for daily series), B ≥ 5,000. Report the 5th percentile of annualised excess return, of Sharpe, and of max drawdown; acceptance: 5th-percentile excess return > 0 (equivalent to a one-sided 5% test without normality assumptions). Also bootstrap the *difference* vs benchmark using the same resampled dates for both series (paired).
- **Drawdown expectations follow from Sharpe.** For an excess-return stream with IR ≈ 0.4 and tracking error 12%, relative drawdowns versus the benchmark of 25-35% over a 15-year span are ordinary, not evidence of failure; the kill rule (B6) must be set wider than that or it will fire on noise.

### Gaps
- No source was fetched for Newey-West (1987), Hansen-Hodrick (1980), Politis-Romano (1994) or the Lo (2002) Sharpe-ratio autocorrelation correction; formulas are standard but uncited.
- The per-stock and per-trade volatility inputs (s ≈ 10-12% per swing trade; idiosyncratic 10%/month) are assumptions; the codebase should measure them from its own trade log and re-run these formulas.

---

## B4. Out-of-sample design: walk-forward, purged/embargoed CV, holdout discipline, regime coverage

### Takeaway
One untouched holdout, looked at once, is worth more than any number of in-sample optimisations; every additional peek converts the holdout into training data and must be counted as a trial. For rules with multi-week holding periods, ordinary k-fold leaks and must be purged and embargoed. A sample that starts after 2009 is essentially a bull-market sample for Taiwan and cannot validate behaviour after market declines, which is exactly where Taiwan momentum has historically failed.

### Cited Findings
- **[verified, secondary]** Purged cross-validation (López de Prado, 2017/2018) is a k-fold variant that removes from the training set any observation whose label window overlaps the test set; an **embargo** additionally drops a buffer of training observations immediately *after* each test block (purging applies on both sides, embargo only after) to prevent leakage through serial correlation. Combinatorial purged CV (CPCV) splits the sample into N contiguous groups and tests on every combination of k groups (C(N,k) splits), yielding a distribution of out-of-sample paths rather than a single path. Primary reference: *Advances in Financial Machine Learning* (Wiley 2018), purge/embargo in ch. 7 and CPCV in ch. 12 (chapter numbers per library docs, not checked against the book). — [Wikipedia: Purged cross-validation](https://en.wikipedia.org/wiki/Purged_cross-validation); [fynance CPCV docs](https://fynance.readthedocs.io/en/latest/generated/fynance.data.combinatorial_purged_cv.html); [purgedcv on PyPI](https://pypi.org/project/purgedcv/)
- **[US][verified]** Harvey & Liu note the trade-off of IS/OOS splits: a true discovery can be missed if the in-sample is too short, and propose using a lenient IS cutoff, checking OOS survival and intersecting with a full-sample multiple-testing adjustment. — [Harvey & Liu, Backtesting](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)
- **[US][verified]** Even a correctly declared number of trials understates the problem because one's work "may be based on prior trials" by other researchers — e.g. a rule inspired by a strategy someone else selected from a million trials. — [False Strategy Theorem paper (referee exchange)](https://escholarship.org/uc/item/95t7k79q)
- **[TW][verified]** Taiwan momentum is state-dependent: more negative after DOWN markets than in the US (Du, Huang & Liao 2009); significantly positive in up markets and negative-insignificant in down markets (Sun, Tsai & Wang 2011). — [IDEAS](https://ideas.repec.org/a/eee/jebusi/v61y2009i2p140-152.html); [MPRA](https://mpra.ub.uni-muenchen.de/37281/1/MPRA_paper_37281.pdf)
- **[TW][verified]** The daily price limit changed from ±7% to ±10% on 1 June 2015 — a structural break inside any 2010-2026 sample. — [TWSE 配套措施簡報](https://www.twse.com.tw/staticFiles/news/event/event_download_201504021124_03.pdf)

### Inferences
- **Recommended split for ~2008/2010-2026 daily data:**
  1. *Design set*: start of data to end-2019 (includes 2008-09 if available, 2011, 2015, 2018 corrections). All rule development and parameter choice happens here, using walk-forward or purged CV.
  2. *Validation set*: 2020-2022 (COVID crash, 2021 retail boom, 2022 bear −~25-30%). May be consulted a small, pre-declared number of times (≤ 3); each look is logged.
  3. *Lockbox holdout*: 2023 to present. Looked at exactly once, after the rule and acceptance criteria are frozen in a committed file. If the rule fails here, it is dead — it is not re-tuned and re-tested on the same lockbox.
  4. *True out-of-sample*: paper trading / small-size live trading going forward, for at least 12 months, compared against the backtest's predicted distribution.
- **Walk-forward protocol:** rolling or expanding training window (e.g. 5 years) → choose parameters by a fixed, pre-declared objective → trade the next 12 months → roll. Concatenate only the out-of-sample segments for evaluation. Report the walk-forward efficiency = OOS annualised excess return / IS annualised excess return; values below ~0.5 indicate overfitting (consistent with the 35-58% decay in McLean-Pontiff as a normal level).
- **Purge/embargo sizes for a swing system:** purge = maximum holding period (e.g. 20-60 trading days) on both sides of each test block; embargo = longest indicator lookback that can carry information forward plus the holding period (if a 120-day momentum lookback is used, features computed just after the test block still contain test-period prices; an embargo of ~1-2× the holding period is the common compromise, with lookback contamination acknowledged). For pure rule-based (non-ML) strategies with few parameters, walk-forward + lockbox is usually sufficient; purged k-fold/CPCV matter once many parameter combinations are being selected.
- **Holdout peeking arithmetic:** if the holdout is consulted k times and the best result kept, the effective hurdle on the holdout t-stat rises as in the Bonferroni table (B2): 5 looks → t 2.58; 10 looks → 2.81. A 3-4-year holdout can rarely deliver t > 2 even once (IR 0.9 × sqrt(3.5) ≈ 1.7), so the holdout's realistic role is *falsification* (does performance collapse or change sign?), not proof. Pre-declare the holdout pass rule in those terms, e.g. "holdout excess return > 0 and ≥ 30% of design-set excess return; max relative drawdown within the bootstrap 95% band".
- **Regime coverage checklist (Taiwan):** require the test period to include and separately report: 2008 (−46% year) if data allow; 2011 (−21%); 2015 (China deval / limit change); 2018 Q4; 2020 Q1 crash and rebound; 2022 bear; 2024-2026 TSMC/AI concentration phase; April 2025 tariff shock. Report conditional performance for months following a negative trailing-12-month market return versus positive — if all the edge sits in the "after up-market" state, the rule is a levered bull-market bet, and a market-regime filter (or acceptance of that risk) must be explicit. (Index-year magnitudes here are approximate recollections, used only to name the episodes.)
- **Yahoo data practical limit:** many .TW histories begin in 2000 or 2007-2008 with gaps; if the usable clean sample starts ~2010, there is no full bear market in the design set except 2011/2015/2018 — flag this as a known limitation in any report rather than hiding it.

### Gaps
- López de Prado's book was not consulted directly; chapter references and the "embargo only after the test set" detail are from secondary sources.
- No empirical study was found quantifying how fast repeated holdout reuse degrades validity for trading strategies specifically (the adaptive-data-analysis literature, e.g. Dwork et al. 2015 "reusable holdout", is relevant but was not retrieved).
- Whether Yahoo Finance .TW/.TWO histories reliably extend before 2008 with correct adjustments was not tested this session.

---

## B5. Look-ahead and execution realism for Taiwan daily data

### Takeaway
The most damaging and most common errors in a Yahoo-based Taiwan backtest are: trading at the same close that generated the signal, using adjusted prices to decide price-level rules, assuming fills on limit-up/limit-down days, and applying today's listed universe to the past. Each can be turned into a mechanical check.

### Cited Findings
- **[TW][verified]** Daily price limit widened from ±7% to ±10% effective 1 June 2015 (odd-lot and block trades also moved from 7% to 10%); margin maintenance ratio raised from 120% to 130% on 4 May 2015 as a companion measure. — [TWSE 配套措施簡報](https://www.twse.com.tw/staticFiles/news/event/event_download_201504021124_03.pdf); [公視新聞](https://news.pts.org.tw/article/298694)
- **[TW][verified]** Intraday odd lots trade by periodic call auction (1-minute interval since 19 Dec 2022; 3 minutes before), first match historically 09:10 (being moved to 09:00), and odd lots account for only ~0.9% of market turnover; odd lots cannot be day-traded. — [CNA](https://www.cna.com.tw/news/afe/202208150262.aspx); [工商時報](https://www.ctee.com.tw/news/20241126700245-430201); [經理人](https://www.managertoday.com.tw/articles/view/59023)
- **[TW][verified]** Sell-side transaction tax 0.3% for stocks, 0.1% for ETFs (relevant when the benchmark is 0050: the benchmark's own trading cost is lower, and a buy-and-hold 0050 investor pays it once). — [Money101](https://www.money101.com.tw/blog/%e8%b2%b7%e8%b3%a3%e8%82%a1%e7%a5%a8%e6%89%8b%e7%ba%8c%e8%b2%bb%e6%80%8e%e9%ba%bc%e7%ae%97%ef%bc%9f%e4%b8%80%e5%bc%b5%e5%9c%96%e8%a1%a8%e8%ae%93%e4%bd%a0%e4%b8%80%e7%9c%8b%e5%b0%b1%e6%87%82)
- **[US][verified]** Omitted delisting returns alone were enough to manufacture a published anomaly (Nasdaq size effect) — data-handling errors are first-order, not cosmetic. — [Shumway & Warther 1999](https://ideas.repec.org/a/bla/jfinan/v54y1999i6p2361-2379.html)

### Inferences (implementation checklist — each item is testable in code)
1. **Signal/trade timing.** Signals computed from day-t close (and volume) may only be executed at day t+1 open or later. Unit test: shift all signals by +1 day and assert identical results to the production path; then shift by +2 and +5 days and report degradation (an edge that vanishes with a 1-2 day delay is not retail-executable). Test both "next open" and "next close" fills.
2. **Adjusted vs unadjusted prices.** Use *adjusted* close (還原權息) for return and momentum calculations; use *unadjusted* OHLC for anything price-level-dependent: limit-up/limit-down detection, tick size, board-lot cost (price × 1,000), price filters (e.g. ≥ NT$10), and gap rules. Yahoo's `Adj Close` is back-adjusted, so historical adjusted prices change every time a dividend is paid: store raw prices + dividend/split events, and never persist signals computed from a past download's adjusted series as "point-in-time". Verify a sample of ex-dividend dates (Taiwan cash dividends cluster in June-September; many stocks pay 3-6% so unadjusted breakout/stop logic will see false gap-downs on 除息 days).
3. **Benchmark must be total return.** Compare against 0050 adjusted close (dividends reinvested) or the TAIEX total return index (報酬指數), never the price-only 加權指數; Taiwan's dividend yield has historically been ~3-4%/yr, so a price-index benchmark hands the strategy that much false alpha when the strategy itself uses adjusted prices.
4. **Price-limit days (±10% since 1 Jun 2015; ±7% before).** Mark day as limit-up-locked if unadjusted close ≥ round-to-tick(prev close × 1.10) and, more strictly, if high = low = limit (一字鎖漲停). Rules: (a) a buy order on a day whose open is at limit-up is **not filled**; (b) a buy at the close on a limit-up close is not filled (queue priority unknown — assume no fill); (c) a sell on a limit-down open/close is not filled and rolls to the next day until the stock trades off the limit; (d) report results under both "optimistic" and "no-fill-at-limit" assumptions — breakout systems are specifically biased here, because the strongest breakout days are the ones a retail order cannot get filled on. Report the share of backtest entries that occurred on limit-up days; if their removal eliminates the edge, the edge is unexecutable.
5. **Suspensions, 全額交割, 處置股 (disposition stocks with 5-/20-minute call auctions and pre-funding), 注意股.** Days with zero volume = no fill. Exclude or penalise names under disposition (much wider effective spread, pre-collected funds). Free flags are published daily by TWSE/TPEx; historical lists may need scraping.
6. **Liquidity and slippage.** Minimum 20-day median traded value (e.g. ≥ NT$20-50M); order ≤ 1% of ADV; slippage per side by tier (assumptions to be calibrated): top-150 by turnover 0.10%, mid 0.20-0.30%, small/odd-lot 0.30-0.50%; on gap days take the worse of open price and signal price. Sensitivity test: double all slippage and require the strategy to remain above the acceptance bar.
7. **Costs.** Commission 0.1425% × discount each side with the broker's minimum fee per order; 0.3% tax on sells; apply at the order level (minimum fee matters for odd lots). Round share counts to tradable units (1 share for odd lots, 1,000 for board lots) and model cash drag.
8. **Universe point-in-time.** For each date, the eligible universe = stocks listed and trading on that date (listing date ≤ date; not yet delisted), including later-delisted codes where data exist (B1). Exclude the first N (e.g. 60-120) trading days after IPO (IPOs traded with no price limit for the first five sessions; momentum signals are undefined). Exclude ETFs, TDRs, warrants, preferred shares, and (optionally) 創新板 / 興櫃.
9. **Corporate-action sanity.** Capital reductions (減資), rights issues and stock dividends (配股) create large raw-price jumps; assert that no single-day *adjusted* return exceeds the limit band (+10.5% / −10.5% post-June 2015) except on documented no-limit days — any violation is a data error to be fixed or the stock-day dropped.
10. **Data-quality audit.** Yahoo .TW data contain occasional zero-volume rows, duplicated days, missing days around typhoon closures, and bad split adjustments; log counts of each and cross-check a random 1% of closes against TWSE daily quotes.

### Gaps
- The current rules for 處置股 matching intervals, IPO no-limit periods (first five trading days) and 全額交割 were not verified against TWSE regulations this session (stated from memory).
- No measured slippage data for Taiwan small caps or odd lots were found; tier values are assumptions.
- No source quantifies how often breakout-day closes in Taiwan are at limit-up (and so unfillable); this should be measured in the dataset — it is likely material for a breakout scanner.
- Yahoo Finance's handling of Taiwan cash/stock dividends and capital reductions in `Adj Close` was not audited this session.

---

## B6. A pre-registered acceptance test for a retail Taiwan long-only momentum/breakout rule

### Takeaway
"Confident" should mean: the rule, frozen in advance, clears every item of a written test whose thresholds were fixed before the final data were examined, with the number of variants tried disclosed. The thresholds below are a synthesis of the evidence in A1-B5 — they are proposals by this researcher, not a published standard.

### Cited Findings
- **[US][verified]** t-ratio > 3.0 as the hurdle for a newly proposed factor. — [Harvey, Liu & Zhu, NBER w20592](https://www.nber.org/papers/w20592.pdf)
- **[US][verified]** Multiple-testing Sharpe haircut is nonlinear: > 50% for SR < 0.4, ≤ 25% for SR > 1.0; an SR 1.0/120-month/100-test example deflates to 0.44. — [Harvey & Liu, Backtesting](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)
- **[US][verified]** The reported Sharpe must exceed the expected maximum Sharpe of the number of trials run; researchers should disclose the full number of trials. — [False Strategy Theorem](https://escholarship.org/uc/item/95t7k79q)
- **[US][verified]** Expect 35-58% decay of anomaly returns after discovery/publication. — [McLean & Pontiff working paper](https://ivey.uwo.ca/media/3775549/pontiff.pdf); [J. Finance record](https://econpapers.repec.org/RePEc:bla:jfinan:v:71:y:2016:i:1:p:5-32)
- **[US][verified]** Strategies with >50% monthly turnover rarely survive costs; buy/hold spreads are the most effective mitigation. — [Novy-Marx & Velikov, NBER w20721](https://www.nber.org/papers/w20721)
- **[TW][verified]** Base rates: individuals lose 3.8 pp/yr in aggregate; <1% of day traders reliably profitable net of fees. — [Barber et al. 2009](https://econpapers.repec.org/RePEc:oup:rfinst:v:22:y:2009:i:2:p:609-632); [Barber et al. 2014](https://econpapers.repec.org/RePEc:eee:finmar:v:18:y:2014:i:c:p:1-24)
- **[Global][verified]** Reference performance of a real long-only momentum index: +2.8 pp/yr gross, TE ~7.5-8%, IR ~0.33-0.38, max drawdown −55.5%. — [MSCI World Momentum factsheet](https://www.msci.com/documents/10199/904e031c-94e4-4dbc-a314-7c373446dffa)

### Inferences — proposed acceptance specification (to be committed to the repo BEFORE the lockbox is opened)

**0. Pre-registration artefacts (pass/fail on existence)**
- `acceptance.yaml` committed with: rule definition, all parameters, universe filter, cost model, benchmark(s), data period split, every threshold below. Git commit hash recorded in the report.
- `trials.log` append-only: every backtest configuration ever evaluated on design/validation data (N_trials). Lockbox access count recorded (must be 1 at acceptance).

**1. Data integrity gates (all must pass before any performance number is read)**
- Signal at close t, fill no earlier than open t+1 (unit-tested by shift test).
- Unadjusted prices for limit/price-level logic; adjusted for returns; benchmark = 0050 total return (adjusted) AND equal-weight universe AND TAIEX total-return index.
- No fills on locked limit-up (buys) / limit-down (sells) days or zero-volume days.
- Point-in-time universe; IPO seasoning ≥ 60 trading days; liquidity filter applied using only past data.
- Costs: commission 0.1425% × actual broker discount with minimum fee, 0.3% sell tax, slippage per tier (base case ≥ 0.2% per side for non-large-caps).
- Data audit: zero adjusted daily returns outside the limit band except documented cases.

**2. Performance thresholds (net of all costs, full design + validation period ≥ 10 years, ≥ 120 monthly observations)**
| # | Criterion | Threshold | Rationale |
|---|---|---|---|
| P1 | Annualised net excess return vs 0050 total return | > 0, and ≥ +3 pp/yr vs equal-weight universe and TAIEX TR | must beat the buy-and-hold alternative the user actually has; ≥ 3 pp so that a 50% live haircut still leaves > 1.5 pp |
| P2 | t-stat of monthly net excess return (Newey-West, lag 3) | ≥ 3.0 if N_trials ≤ 20; otherwise ≥ Bonferroni hurdle Φ⁻¹(1 − 0.025/N_trials) (3.29 at 50; 3.48 at 100) | Harvey-Liu-Zhu |
| P3 | Deflated Sharpe Ratio of excess returns using N_trials | ≥ 0.95; equivalently annualised IR > expected-max hurdle (0.50 / 0.60 / 0.72 / 0.80 for 10 / 20 / 50 / 100 trials on 10 yrs) | Bailey-López de Prado |
| P4 | Stationary block-bootstrap (5,000 draws, mean block 3 months) 5th percentile of annualised net excess return | > 0 | distribution-free one-sided 5% test |
| P5 | Rolling 3-year windows (monthly step) with positive net excess return vs 0050 TR | ≥ 65% of windows; no rolling 5-year window worse than −5 pp/yr | at a true IR 0.4-0.5, 76-81% of 3-yr windows are expected positive; 65% allows sampling noise |
| P6 | Calendar years beating benchmark | ≥ 55% | Φ(IR) for IR ≈ 0.15+ ; weak filter, catches one-year wonders |
| P7 | Maximum drawdown (absolute) | ≤ 1.25 × benchmark max drawdown over the same period, and ≤ 45% | long-only momentum does not reduce drawdown (MSCI: −55.5%) |
| P8 | Maximum relative drawdown vs benchmark | reported; ≤ 35% | sets the live kill-rule width |
| P9 | Concentration of profits | removing the top 5 trades (or top 1% of trades) leaves net excess return > 0; no single stock contributes > 25% of total profit | Bessembinder skew: result must not depend on one outlier (e.g. one AI-cycle multibagger) |
| P10 | Turnover | one-way ≤ 400%/yr (≤ 33%/month); report gross vs net | Novy-Marx-Velikov |
| P11 | Number of trades and breadth | ≥ 300 closed trades and ≥ 100 distinct stocks over the test period; average ≥ 12 concurrent holdings | B3 sample size; A1 breadth |

**3. Robustness gates**
- R1 Parameter perturbation: vary each parameter ±20% (and lookbacks by ±1 step) one at a time and jointly on a small grid; ≥ 80% of neighbours keep net excess return > 0, and the median neighbour achieves ≥ 60% of the chosen configuration's excess return. A sharp peak = overfit.
- R2 Cost stress: slippage doubled and commission at the undiscounted 0.1425% → net excess return still > 0.
- R3 Execution delay: fills delayed by 1 additional day → ≥ 60% of excess return retained.
- R4 Rebalance-offset: all rebalance-day offsets (each weekday / each of ~20 monthly offsets) → worst offset still > 0 net excess; report best-worst spread.
- R5 Sizing: passes under both equal weight and inverse-vol (capped) weighting.
- R6 Sub-periods: positive net excess return in each of ≥ 3 non-overlapping sub-periods (e.g. 2010-2014, 2015-2019, 2020-2022) and in both pre- and post-June-2015 price-limit regimes; separately report months following negative vs positive trailing-12-month market return — loss in the "after down market" state must be bounded (e.g. ≥ −5 pp/yr relative).
- R7 Survivorship stress: on a delisted-inclusive dataset if obtainable; otherwise inject synthetic failures — each year, randomly force k = 2-3% of open positions to a −70% terminal return — net excess return remains > 0 in ≥ 90% of 1,000 simulations.
- R8 Ex-TSMC attribution: report excess return vs a benchmark with TSMC capped at 30% (or 00850 / equal-weight top 50) for 2023-2026 so that TSMC under/overweight is not mistaken for skill.
- R9 Random-entry placebo: replace the entry signal with random entries matched in count, timing distribution and holding period (1,000 runs, same exits/sizing/costs); the real rule's net return must exceed the 95th percentile of the placebo distribution. This isolates the entry signal's contribution from market beta and exit/sizing effects.
- R10 Small-book realism: re-run with N = 5, 10, 15, 20 randomly selected signals when more signals than slots exist (1,000 draws each); report the distribution — the 25th-percentile path at the user's actual slot count must still have net excess return ≥ 0.

**4. Lockbox (2023-present), examined once**
- L1 Net excess return vs 0050 TR > 0 OR, if negative, within the 10th-90th percentile band of what the design-period bootstrap predicts for a window of the same length (so a real-but-unlucky edge is not rejected mechanically), AND net excess return vs equal-weight universe > 0.
- L2 Realised excess return ≥ 30% of design-period excess return (walk-forward efficiency).
- L3 Max drawdown and turnover within 1.25× of design-period values.
- Fail → rule is retired; any modified rule is a new trial requiring a new, later lockbox (i.e. forward paper-trading).

**5. Live monitoring / kill rule (post-acceptance)**
- Paper or minimum-size live trading for ≥ 12 months; compare monthly to the backtest's bootstrap bands.
- Stop trading the rule if the cumulative live relative return falls below the 2.5th percentile of the bootstrap-predicted path for that horizon, or relative drawdown exceeds 1.5 × P8.
- Wording for the final report: state the estimated edge with its confidence interval and the probability of underperforming 0050 over 1, 3 and 5 years (IR table in A4) — never "this rule works".

**Expected outcome, stated plainly:** given A4's realistic IR of 0.35-0.5 and ~10-15 years of data, an honest long-only momentum rule will often FAIL P2/P3 (t ≥ 3 requires IR ≥ 0.8-0.95 on 10-14 years). Two legitimate responses: (i) accept a lower evidential tier — "consistent with a real edge, not proven" (e.g. t ≥ 2 with ≤ 5 trials, all robustness gates passed, plus external evidence that the same rule works in other markets/periods) and size it accordingly (e.g. half the capital, remainder in 0050); or (ii) lengthen/broaden the test (TPEx names, earlier years, other Asian markets) to gain independent observations. What is not legitimate is tuning until P2 passes.

### Gaps
- No published, authoritative "retail strategy acceptance standard" was found; the thresholds above are this researcher's synthesis and should be presented as such. In particular the numeric choices in P5-P11 and R1-R10 (65% of windows, ±20% perturbation, 80% of neighbours, 2-3% synthetic failure rate, 300 trades) are judgment calls anchored to the calculations in A1, A4, B2 and B3, not values taken from a source.
- Whether a delisted-inclusive free dataset can actually be assembled for Taiwan (R7) is unresolved (see B1 gaps); the synthetic-failure test is the fallback.
- The PSR/DSR formula needed for P3 must be checked against the original paper before implementation (B2 gaps).
