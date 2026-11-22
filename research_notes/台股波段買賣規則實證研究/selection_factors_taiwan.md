# Stock-Selection Factors with Empirical Evidence in Taiwan (TWSE/TPEx), as of Nov 2026

Reader notes on evidence quality (applies to every section):
- **[PR]** = peer-reviewed journal; **[TH]** = master's/PhD thesis or conference paper; **[WP]** = working paper; **[V]** = vendor / broker / blog backtest (not independently verified).
- **(abstract only)** = I could only read the abstract or an index page (paywall); the effect sizes are NOT in my notes because they were not visible, not because they are zero. **(full text)** = I read the numbers in the paper itself.
- Almost all academic results are **long-short, gross of costs**. Almost none report a long-only, net-of-cost result versus TAIEX total return / 0050. This is the single biggest gap for the intended use.
- Retail round-trip cost baseline used in my inferences: 0.1425% x 2 brokerage + 0.3% sell tax = 0.585% before slippage (figures given in the assignment; brokerage discounts lower it, slippage raises it).

---

## 1. Price momentum (12-1 / Jegadeesh-Titman) in Taiwan

### Takeaway
Unconditional classic momentum is weak to absent in Taiwan; this is the consensus of at least six peer-reviewed Taiwan papers (2009-2024), which all start from "Taiwan is an exception to momentum" and then show it reappears only conditionally: in UP / persistent market states, after removing extremely volatile ("extreme absolute strength") stocks, for "persistent" winners, or with volatility management. A plain "buy the 12-1 top decile" rule has no robust Taiwan support.

### Cited Findings
- [PR, abstract only] Du, Huang & Liao (2009, *Journal of Economics and Business* 61(2):140-152), "Why is there no momentum in the Taiwan stock market?": DOWN markets occur more often in Taiwan than in the US, and momentum profits after DOWN markets are more negative in Taiwan than in the US; authors attribute the absence of momentum to state-dependence (Cooper, Gutierrez & Hameed 2004) rather than culture. Sample period and magnitudes not visible. — [NAU research portal](https://experts.nau.edu/en/publications/why-is-there-no-momentum-in-the-taiwan-stock-market/)
- [PR, abstract only] Lin, Ko, Feng & Yang (2016, *Pacific-Basin Finance Journal* 38:59-75), "Market dynamics and momentum in the Taiwan stock market": no unconditional momentum premium; **significantly positive momentum profits when the market stays in the same state (continuation), significant reversals when the market transitions between states**; profits concentrated in high-investor-attention stocks. No magnitudes visible. — [IDEAS](https://ideas.repec.org/a/eee/pacfin/v38y2016icp59-75.html)
- [PR, abstract only] Lin, Xia, Yang & Yang (2020, *Pacific-Basin Finance Journal* 59), "Enhancing momentum profits in the Taiwan Stock Market: The role of extreme absolute strength": stocks with extreme absolute past returns are highly volatile and attenuate momentum; removing them from winner and loser portfolios improves momentum profits and lowers volatility. A search-engine summary attributes to this paper a plain Jegadeesh-Titman return of **-0.158% per month (insignificant) with a 6-month holding period** — I could not open the full text to verify that number. — [IDEAS](https://ideas.repec.org/a/eee/pacfin/v59y2020ics0927538x19303993.html); [CORE copy (blocked to me)](https://core.ac.uk/download/343511119.pdf)
- [PR, abstract only] Chen, Hsieh & Lee (2023, *Pacific-Basin Finance Journal* 78), "Revisiting the momentum effect in Taiwan: The role of persistency": high turnover of names in winner/loser portfolios weakens momentum in Taiwan; a strategy that buys **persistent winners** (stocks that stay in the winner group) and shorts persistent losers earns significant intermediate-term profits; persistency is related to heterogeneous beliefs. No magnitudes visible. — [IDEAS](https://ideas.repec.org/a/eee/pacfin/v78y2023ics0927538x23000094.html)
- [PR, abstract only] Lin, Ko & Yang (2022, *Pacific-Basin Finance Journal* 72), "Does the momentum gap explain momentum in Taiwan?": the momentum gap (Huang 2021) does **not** predict momentum returns in Taiwan; authors link this to daily price limits. — [IDEAS](https://ideas.repec.org/a/eee/pacfin/v72y2022ics0927538x22000270.html)
- [PR, abstract only] Chiang, Chiu & Hsu (2024, *Pacific-Basin Finance Journal* 83), "Retrieving almost stochastic dominance momentum in Taiwan stock market": ASD-based momentum has better risk-adjusted performance, lower volatility and less negative skew than classic momentum; effect strongest at **shorter ranking and holding periods**; abnormal returns survive common factor models. No magnitudes visible. — [IDEAS](https://ideas.repec.org/a/eee/pacfin/v83y2024ics0927538x24000192.html)
- [WP, full text read in part] Sun, Tsai & Wang (2011, MPRA 37281), TSE stocks, **weekly data, 1 Jan 1998 - 31 Aug 2008**, 100 formation x holding combinations, long-short, gross: 54 of 100 strategies have positive average weekly returns significant at 1% over all states; **in UP markets 76 of 100 are significant at 1% (only 6 not significant); in DOWN markets only 6 of 100 are significantly positive at 1%**. Strategies with holding periods longer than 8 weeks are positive, but only when formed on very short (<=2 weeks) or very long (>=36 weeks) returns; **formation 3-24 weeks with holding <4 weeks gives no significant return**. Under a stricter statistical-arbitrage test only 17 of 100 pass in all states vs 58 in UP markets. Authors attribute UP-market momentum to institutional overconfidence. — [MPRA paper 37281](https://mpra.ub.uni-muenchen.de/37281/1/MPRA_paper_37281.pdf)
- [PR, search summary only] A 2026 *Journal of Risk and Financial Management* (MDPI, vol. 19 issue 7) paper with a **Jan 1993 - Dec 2025** Taiwan sample reports that volatility management enhances momentum profitability in Taiwan. Page returned HTTP 403; no numbers verified. — [MDPI](https://www.mdpi.com/1911-8074/19/7/462)
- [PR, secondary source] Chui, Titman & Wei (2010, *Journal of Finance* 65(1):361-392): momentum profits rise with a country's individualism score; a secondary source states momentum returns are insignificantly different from zero for Taiwan (and China, Indonesia, Japan, Korea, Malaysia, Philippines, Singapore, Thailand). Exact Taiwan monthly figure not verified. — [EconPapers record](https://econpapers.repec.org/RePEc:bla:jfinan:v:65:y:2010:i:1:p:361-392); [secondary source](https://eprints.whiterose.ac.uk/id/eprint/136438/15/Cognitive%20dissonance%20and%20the%20%20above%20suspicion%20anomalies%20full%20paper%2020181008%20EFM%20style%20final.pdf)
- [PR, secondary source; NOT Taiwan-specific] Fama & French (2012, *JFE* 105:457-472) find no momentum in Japan. — [secondary source](https://thesis.eur.nl/pub/53133/Thesis.pdf)
- [V] TEJ "volatility-adjusted momentum" (VAM = 21-trading-day cumulative return / same-window daily return std), universe = Taiwan Mid-Cap 100 constituents with liquidity filter, top 10 equal weight, monthly rebalance plus dynamic exposure reduction, **30 Dec 2019 - 31 Dec 2024 (1,218 days), net of 0.1425% each way + 0.3% tax and a slippage model**: annualized return **43.84% vs TAIEX 18.43%**, vol 28.97% vs 18.60%, Sharpe 1.40 vs 1.00, **max drawdown -34.55% vs -28.55%**, beta 0.95; by year 2021 +133.22%, 2022 -22.80%, 2023 +96.21% (TAIEX +31.48%), **2024 +24.17% (TAIEX +31.73%, i.e. underperformed)**; monthly win rate 57.38%, worst month Mar 2020 -16.43%. — [TEJ via LINE TODAY](https://today.line.me/tw/v3/article/eL5pGnB)
- [V] Another TEJ article: pure momentum annualized 12.7%, Sharpe 1.01; adding a short-interest-ratio (借券放空比率) filter that excludes heavily shorted stocks raised it to 21.7%, Sharpe 1.83; effect strongly size-dependent. Period/universe not captured. — [TEJ via LINE TODAY](https://today.line.me/tw/v3/article/NvVY151)

### Inferences
- For a long-only swing trader, raw relative-strength ranking should be treated as a **conditional** signal: use it only when the market is in an up state and has not just changed state (e.g. index above its own long moving average / positive trailing index return, the Cooper-Gutierrez-Hameed definition used by Sun et al. and Du et al.). The exact up-state threshold that works best in Taiwan is not established by what I could read.
- Three independent Taiwan papers point to the same practical modification: exclude the most extreme / most volatile past winners (Lin et al. 2020), prefer winners that keep re-qualifying (Chen et al. 2023), and scale by volatility (MDPI 2026; TEJ VAM). A testable rule: rank on return / volatility, drop the top few percent of raw-return outliers, require the stock to have been in the winner group for 2+ consecutive ranking dates.
- The TEJ VAM backtest is a 5-year, bull-dominated, mid-cap, 10-stock sample with a larger drawdown than the index and a losing relative year in 2024; it is weak evidence of persistent edge and likely overstated relative to a longer sample.
- Sun et al.'s finding that 3-24 week formation with <4 week holding earns nothing is directly relevant to the 2-week end of the user's holding range: very short holds on intermediate-term momentum have no support.

### Gaps
- No verified Taiwan-specific monthly WML magnitude and t-stat from a peer-reviewed full text (all the *PBFJ* papers were paywalled). The -0.158%/month figure is unverified.
- No Taiwan evidence I could read on **long-leg-only** momentum returns versus the market, nor net of costs.
- No Taiwan-specific replication of Daniel & Moskowitz (2016) momentum-crash statistics was found; crash risk is inferred only from the market-transition reversals in Lin et al. (2016) and the down-market losses in Du et al. (2009).
- Post-2020 decay or strengthening (retail boom, day-trading tax cut, AI-led concentration) is not covered by any peer-reviewed source I could read except the unverified MDPI 2026 paper.

---

## 2. 52-week-high momentum (George & Hwang 2004) in Taiwan

### Takeaway
The 52-week-high (nearness to high) signal is the best-supported price-momentum variant in Taiwan: Hao et al. (2016) find it "plays a determinant role in generating momentum returns" over 1982-2012, but its profits are damaged by strongly negative January returns, and thesis evidence finds it is not clearly better than other momentum at 6-month horizons. Effect sizes and net-of-cost results were not obtainable.

### Cited Findings
- [PR, abstract only] Hao, Chu, Ho & Ko (2016, *International Review of Economics & Finance* 43:121-138), Taiwan, **Jan 1982 - Dec 2012**: the 52-week-high strategy drives momentum returns over 1982-2012 when strategies are run jointly; its profits are **weakened by strongly negative January returns**; the competing "recency" strategy (how recently the high was set) is profitable **only before 2000, in expansions, and in up-market states** and dominated in the 1970s. Authors conclude anchoring and recency biases coexist. — [EconPapers](https://econpapers.repec.org/RePEc:eee:reveco:v:43:y:2016:i:c:p:121-138)
- [PR, abstract only] Liao, Chang & Wang (2023, *IJBESAR* 16(1)): decomposing price/52-week-high into a price-change part and a high-updating part, the subsequent positive momentum of the winner portfolio is stronger when a high ratio results from a downward update of the 52-week high (old high rolling out of the window) — i.e. not all "near the high" stocks are equal. — [IJBESAR PDF](https://ijbesar.ihu.gr/docs/volume16_issue1/16_01_07.pdf)
- [TH] Yu (2022, NTU master's thesis), TWSE stocks, stochastic-dominance comparison: at a 6-month holding period there is **no evidence the 52-week-high strategy is significantly better** than individual-stock or industry momentum; at 12 months it dominates (almost first-order, and first-order against 12-month individual momentum). — [NTU repository](https://tdr.lib.ntu.edu.tw/handle/123456789/84014?locale=en)
- [PR, abstract only] A 2011 *Journal of International Financial Markets, Institutions and Money* (21(1):14-27) paper studies the relationship between individual stocks' 52-week highs and the Taiwan index level. Findings not read. — [IDEAS](https://ideas.repec.org/a/eee/intfin/v21y2011i1p14-27.html)
- [TH] A Kaohsiung-based study of TWSE non-financial stocks, **2008Q1 - 2019Q2**, links post-earnings-announcement drift to 52-week-high anchoring; drift is stronger among stocks with low foreign ownership. — [Journal of Economics and Management, FCU](https://jem.fcu.edu.tw/assets/jem/past_issues/vol.17_no.1/Abstract/vol.17_no.1_01_Abstract.html)

### Inferences
- "Price within X% of 52-week high" is a defensible primary price filter for Taiwan, more so than 12-1 return rank, but the advantage over other momentum appears at 12-month holds, longer than the user's 2-week to 3-month window (Yu 2022). Expect a smaller edge at swing horizons.
- The January effect on this strategy implies testing a seasonal variant: reduce or skip new 52-week-high entries held across January (year-end loser rebound hurts the short leg in long-short tests; for long-only the damage is to relative, not necessarily absolute, performance — this needs to be checked in a backtest).
- Combining 52-week-high nearness with an earnings or revenue surprise is supported by the anchoring-PEAD link: good news arriving when price is near its high is under-reacted to.

### Gaps
- Monthly return, t-stat, and transaction-cost survival for the Taiwan 52-week-high strategy: not visible in any source I could open.
- Liu, Liu & Ma (2011) international 52-week-high evidence: not retrieved; I cannot state their Taiwan figure.
- No Taiwan study of 52-week-high conditional on market state other than the "recency" result in Hao et al.
- No post-2012 peer-reviewed out-of-sample test found.

---

## 3. Monthly revenue momentum / revenue surprise

### Takeaway
This is the strongest Taiwan-specific fundamental signal in the literature: standardized unexpected revenue (SUR) sorts earn significant positive returns for holding periods of 1-12 months (Ku 2010), the effect survives controls for price and earnings momentum, and prices drift in the direction of the monthly revenue surprise until the quarterly earnings announcement (Chen & Yu 2022). Part of the reaction, however, occurs before and at the announcement, and the drift reverses in months 25-36.

### Cited Findings
- [PR, search summary of abstract; full text paywalled] 顧廣平 Ku (2010, 《管理學報》), 〈營收動能策略〉: buying the top 20% and shorting the bottom 20% by standardized unexpected revenue earns **significantly positive average returns for holding periods of 1 to 12 months**; the effect remains after controlling for past returns and unexpected earnings (so it is not just price or earnings momentum); the portfolio shows **significantly negative cumulative returns in holding months 25-36** (long-run reversal, consistent with behavioural over-reaction). Magnitudes not visible. — [月旦知識庫 record](https://lawdata.com.tw/tw/detail.aspx?no=246130); [author page, TKU](https://teacher.tku.edu.tw/StfFdDtl.aspx?tid=399664)
- [PR, search summary] 顧廣平 & 卓志文, 〈產業營收動能策略〉: industry-level revenue momentum is almost entirely explained by stock-level revenue momentum, not the reverse. — [author page, TKU](https://teacher.az.tku.edu.tw/StfFdDtl.aspx?tid=399666)
- [TH/PR, search summary] A ~2020 study finds both **revenue momentum and revenue-new-high momentum (營收創新高動能)** produce significantly positive returns that three-factor models and macro risk do not explain; revenue momentum shows a later price reversal correcting over-reaction. — [Airiti record](https://www.airitilibrary.com/Article/Detail/U0002-2207202009464900)
- [PR, abstract only] Chen & Yu (2022, *Review of Quantitative Finance and Accounting* 58(1):245-295), Taiwan mandatory monthly revenue reports: revenue surprises predict future earnings surprises beyond analyst forecasts; **stock prices drift positively with revenue surprises before the quarterly earnings announcement, and the drift disappears at the earnings announcement**. Sample period and return magnitudes not visible. — [IDEAS](https://ideas.repec.org/a/kap/rqfnac/v58y2022i1d10.1007_s11156-021-00994-1.html)
- [PR, abstract only] A 2024 *International Journal of Accounting* paper: monthly sales news pre-empts late quarterly earnings; earnings-announcement returns and post-earnings drift are weaker when earnings come late and monthly sales already revealed the news. — [IDEAS](https://ideas.repec.org/a/wsi/tijaxx/v59y2024i01ns1094406024500021.html)
- [TH, full text] 沈勤瑋 Shen (2015, NTU master's thesis), TWSE-listed firms, **2013-2014, 18,782 firm-month announcements using actual announcement dates**, CAR over event day and next day: revenue response coefficient **1.5557**, significantly positive; 18 of the industries tested have positive significant coefficients; **bad news elicits a stronger reaction than good news** (bad 1.0458 vs good 0.9813 in separate regressions); persistent news matters more than non-persistent (persistent bad 2.1784, non-persistent bad 1.9547, non-persistent good 1.2159, all significant). — [NTU thesis PDF](https://tdr.lib.ntu.edu.tw/jspui/bitstream/123456789/4740/1/ntu-104-1.pdf)
- [TH, search summary] A thesis on 2013-2021 data: significantly positive abnormal returns **both before and after** the announcement date for revenue-record-high events; the effect is positively related to the ratio of the month's revenue to its historical high, negatively related to revenue scale (firm size), and stronger in electronics. — [Airiti record](https://www.airitilibrary.com/Article/Detail/U0002-0705202317354900)
- [TH, search summary] Electronics-sector study: large revenue jumps/drops produce clear post-announcement abnormal returns, but prices already show abnormal returns **5 days before** the announcement. — [NHU journal PDF](https://libap.nhu.edu.tw:8081/Ejournal/3092030204.pdf)
- [TH, search summary] Chiu (2020, NCCU thesis), TWSE + TPEx, **2015-2019**: abnormal returns around announcements; the effect of unexpected revenue is not significant in some industries, including biotech and e-commerce. — [NCCU repository](https://nccur.lib.nccu.edu.tw/handle/140.119/130488)
- [PR, abstract only] Wang & Lien (2022, *RQFA* 59(2)): the negative return to stocks with many limit-up hits (a MAX/lottery effect) becomes insignificant when the limit hits are driven by revenue announcements — i.e. revenue-driven spikes are not followed by the usual lottery-stock underperformance. — [Springer](https://link.springer.com/10.1007/s11156-022-01051-1)
- [V] cnyes 鉅亨易策略: monthly-revenue-growth scoring, buy top 5, monthly rebalance, 10-year backtest annual return **33.92% (incl. dividends) vs market 12.65%**; no drawdown or cost detail captured. — [cnyes](https://hao.cnyes.com/post/9356)
- [V] cnyes 鉅亨易策略: "monthly revenue at 4-year high + institutional (投信) buying" 10-year annualized **23.57% vs index 12.59%**. — [cnyes](https://hao.cnyes.com/post/6318)
- [V] CMoney marketing article: a portfolio of monthly revenue-new-high stocks returned 586% in a 6-year backtest; article itself notes large drawdowns in bear markets and ~1-month holding; no cost or method disclosure. — [CMoney](https://www.cmoney.tw/notes/note-detail.aspx?nid=829730)

### Inferences
- Backtestable definitions with academic backing: (a) SUR = (revenue_t - revenue_{t-12}) / std of that seasonal difference over trailing months, top quintile; (b) monthly revenue at an N-month high (with the revenue/historical-high ratio as a strength score); (c) persistence = second or third consecutive positive surprise (Shen 2015 shows persistent news gets the larger response).
- Timing: the drift window with academic support runs from the monthly announcement (by the 10th) until the next quarterly earnings announcement (Chen & Yu 2022), which fits a 2-week to 3-month hold. Do not hold on the revenue thesis past 12 months (Ku's reversal in months 25-36 and "1-12 months" profit window).
- Because part of the move precedes the announcement (5-day run-up; significant pre-announcement CAR), entering after the announcement captures only the residual drift. Any backtest must use the actual announcement date, not month-end, to avoid look-ahead bias — the pre-2015 literature could not, and Shen (2015) explicitly flags this as a flaw of earlier work.
- The effect is stronger in smaller firms and electronics; exclude or separately test biotech/e-commerce where revenue surprise is uninformative.
- Vendor claims of 24-34% annualized for revenue + trend/institutional combinations are gross-style, short-list (5 stocks), in-sample results from 2010s-2020s bull markets; they should be treated as upper bounds, not expectations.

### Gaps
- Monthly long-short and long-leg return magnitudes and t-stats for Ku (2010), and the sample period of Ku (2010) and Chen & Yu (2022): not visible.
- No peer-reviewed test of **revenue momentum x price momentum double sort** magnitudes was readable (Ku's control tests exist but numbers unavailable).
- No FinLab (finlab.tw) write-up was retrievable through search; I have no FinLab numbers to report.
- Decay risk: revenue momentum has been public since 2010 and is now a standard screen on every Taiwan retail platform; no post-2020 peer-reviewed out-of-sample check found.

---

## 4. Institutional flows (三大法人) and margin trading

### Takeaway
Institutions as a group profit at individuals' expense in Taiwan (Barber et al. 2009), with foreigners capturing nearly half of institutional profits at a six-month horizon, but simple "follow the published net-buy list" rules have mixed and mostly thesis-level support; investment-trust (投信) buying appears informative only at short horizons. I found no rigorous Taiwan study showing that a stock's high margin balance predicts poor returns.

### Cited Findings
- [PR, full text] Barber, Lee, Liu & Odean (2009, *Review of Financial Studies*), complete TSE trade history **1 Jan 1995 - 31 Dec 1999**: the aggregate individual-investor portfolio suffers an **annual performance penalty of 3.8 percentage points**; losses equal 2.2% of Taiwan GDP; virtually all individual losses come from aggressive (marketable) orders; **institutions gain 1.5 percentage points per year after commissions and transaction taxes**; all four institutional groups (corporations, dealers, foreigners, mutual funds) gain; **foreigners earn nearly half of institutional profits when trades are tracked over six months, but only about one-quarter at shorter horizons**; institutional profits accrue within weeks of trade and reach an asymptote at about six months (horizons analysed: 1, 10, 25, 140 trading days). — [Barber et al. 2009 PDF](https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/justhowmuchdoindividualinvestorslose_rfs_2009.pdf)
- [PR/WP] Barber, Lee, Liu & Odean day-trading studies, Taiwan **1992-2006**: day traders' aggregate performance net of fees is negative in each of the 15 years; **fewer than 1% of day traders (about the top 4,000 by prior-year profit) earn reliably positive returns afterward**; losing day traders persist at nearly the same rate as winners. — [Day Trading Skill PDF](https://faculty.haas.berkeley.edu/odean/papers/day%20traders/Day%20Trading%20Skill%20110523.pdf); [JFM 2014 record](https://ideas.repec.org/a/eee/finmar/v18y2014icp1-24.html)
- [TH/conference, full text] 林財印 & 鄭琬齡 (NKUST), TEJ data, **Jan 2005 onward, 1,493 trading days (~2005-2010)**, portfolios of stocks with 5/7/9 consecutive days of net buying or selling by each institution type. Foreign consecutive-buy portfolios: abnormal return about **+1% at 1 month, +4.7% to +5.4% at 3 months, +8.4% to +9.4% at 6 months, +12.3% to +13.3% at 1 year**. But foreign consecutive-**sell** portfolios also earned positive and larger abnormal returns (**+2.3% to +2.5% at 1 month, +5.6% to +6.2% at 3 months, ~+10% at 6 months**), so the buy-minus-sell zero-investment portfolio was significantly **negative** (5-day: -1% at 1 month, -0.7% at 3 months; 9-day: -2% at 1 month, -3.7% at 3 months). Dealer zero-investment results are erratic (e.g. 5-day: +0.2% at 1 month, -2% at 6 months). Authors' reading: 投信 buying has an information advantage **only in the short run** (longer holding does not add return); 投信 selling is uninformative because of redemption pressure. — [NKUST paper PDF](https://dba.nkust.edu.tw/uploads/asset/data/622ab62d2e63565d81a9e2ee/33.pdf)
- [TH, cited inside the NKUST paper] 郭富源 (2007), 2003-2006: a portfolio of the top-10 foreign net-buy stocks held 1-3 months did not beat the Taiwan 50 index — foreign net-buy rankings "did not contain information". — [NKUST paper PDF](https://dba.nkust.edu.tw/uploads/asset/data/622ab62d2e63565d81a9e2ee/33.pdf)
- [TH] NTU master's thesis (2021): using foreign institutional net buying/selling as a signal earned excess returns in both bull and bear markets (more in bull), with positive CAPM alpha; but **persistence of foreign buying/selling in a given stock is valid for only one day**. — [NTU repository](https://tdr.lib.ntu.edu.tw/handle/123456789/74582?locale=en)
- [PR (Taiwan journal), search summary; PDF 404 for me] NYCU-hosted order-level study: foreign trades have the strongest price impact; **investment trusts have the stronger short-term information advantage**; the same-day positive relation between institutional net buying and returns comes largely from positive-feedback trading and price pressure rather than prediction. — [NYCU repository PDF](https://ir.lib.nycu.edu.tw/bitstream/11536/108010/1/10239863-01501-89.pdf)
- [V] Broker (SinoPac/XQ) article: buying stocks that 投信 are buying "fast and heavily", entering next day and holding 15 days, backtested at 56% annualized — unverified vendor claim, no cost/period detail. — [sinotrade](https://www.sinotrade.com.tw/richclub/XQ-Gold/video/-65f7f3da25fedf86eceaf368)
- [Official commentary] TWSE Market Insights (2026): as of end-July 2026 individuals accounted for **more than 98% of margin trading**; TWSE states the market had not experienced widespread or cascading forced liquidations. — [TWSE Market Insights](https://www.twse.com.tw/market_insights/en/detail/8a8216d6a0bdcc0001a0d2d9db47007c)
- [Official commentary citing research] A TWSE Market Insights piece by an NCCU professor: rising margin balances signal retail bullishness and leverage/liquidity risk; research cited there finds aggregate **short** positions (securities lending/short selling) negatively predict future market returns and are more forward-looking than margin data. — [TWSE Market Insights](https://www.twse.com.tw/market_insights/en/detail/8a8216d69e6379f4019e8ba6aa830118)

### Inferences
- The NKUST result that both foreign-buy and foreign-sell portfolios show positive "abnormal" returns, with sell > buy, indicates either a weak benchmark adjustment or mean reversion after foreign selling during 2005-2010 (which includes the 2008-09 crash and rebound). It should be read as: **consecutive-day foreign net buying is not a reliable standalone long signal**, and stocks foreigners dumped rebounded more.
- Reconciling Barber et al. (institutions win) with the weak "follow the list" results: institutional profits come from their actual trade prices and timing; a retail trader acting on end-of-day published totals buys after the price impact. Edge from copying is therefore smaller and short-lived (NTU 2021: one-day persistence).
- 投信 net buying is the most plausible flow signal for 2-week to 1-month swings in small/mid caps (short-term information advantage in two sources), best used as a confirmation alongside revenue surprise rather than alone; it should be scaled by shares outstanding or volume, and tested with an explicit exit at ~15-20 trading days because the advantage does not grow with holding period.
- Margin data: since >98% of margin is retail and retail trades lose in aggregate, a high or fast-rising margin ratio (融資使用率) is a reasonable **negative filter to test**, but this is an inference, not a documented Taiwan cross-sectional result.
- Barber et al.'s 1995-1999 sample predates the large rise in foreign ownership and algorithmic trading; magnitudes have probably changed, though the direction (retail aggressive orders lose) is corroborated by later day-trading samples through 2006.

### Gaps
- No peer-reviewed Taiwan study with magnitudes for "投信 net buying of small/mid caps predicts returns over N days" was retrievable.
- No rigorous Taiwan cross-sectional evidence that stock-level margin balance / margin utilisation predicts returns; the search surfaced only news and commentary.
- No evidence on securities-lending short interest as a stock-level long-side filter beyond one TEJ vendor article (section 1).
- Post-2017 day-trading tax halving and the 2020-2026 retail surge are not covered by the academic flow studies I could read.

---

## 5. Value, quality/profitability, low-volatility, size, short-term reversal

### Takeaway
Thesis-level Taiwan evidence says value and quality/profitability are the most stable characteristics, size and value premia are concentrated in small caps, profitability/investment explanatory power is concentrated in large caps, and a low-volatility anomaly exists (best captured with 1-month idiosyncratic volatility). I found no peer-reviewed full-text effect sizes for any of these, and nothing usable on short-term reversal.

### Cited Findings
- [TH] NCCU thesis, all listed and delisted Taiwan firms, **1983-2024**, Fama-French and q-factor models: **size and value premia are primarily driven by small caps; investment and profitability explanatory power is heavily concentrated in large caps**. — [NCCU repository](https://nccur.lib.nccu.edu.tw/handle/140.119/145779)
- [TH] NCU thesis, **1990-2020**: the five-factor model reduces the three-factor model's unexplained intercepts mainly for poorly performing portfolios; profitability loads significantly negatively on the weakest portfolios; **in Taiwan, higher investment goes with higher returns, the opposite of Fama-French (2015)**. — [NCU thesis](https://etd.lib.ncu.edu.tw/thesis/detail/e61ce5f5dbba4c3fac583330c3c986e5)
- [TH] NCCU master's thesis (2017): **long-only** portfolios selected on size, book-to-market and profitability earned significant excess returns in Taiwan, and the combined multi-factor portfolio was best. Magnitudes not captured. — [NDLTD record](https://openaccess.library.uitm.edu.my/Record/ndltd-TW-106NCCU5305034/Details)
- [TH] NCCU thesis using TEJ data, **2010-2025, 52 firm-level factors**: **value and quality factors have the best information coefficients and information ratios; momentum, size and risk-oriented factors are more volatile**; a LightGBM combination gave 15.90% annualized, Sharpe 2.50, max drawdown -5.90% for the full-market sample — **transaction costs not included** (and these look like long-short or market-neutral figures; treat with caution). — [NCCU thesis](https://thesis.lib.nccu.edu.tw/thesis/detail/cf3746d1cb1f3395292698a356f29edd)
- [TH] NCCU thesis on low volatility: Taiwan has a significant low-volatility anomaly — low-vol portfolios' excess returns clearly exceed high-vol portfolios' under several multi-factor models; the gap **shrinks as the volatility estimation window lengthens**; low-vol portfolios still deliver positive returns when market risk rises; holdings concentrate in textiles, cement, food. — [NCCU thesis](https://thesis.lib.nccu.edu.tw/thesis/detail/ecbbb1d19b283c677ab4ed946692b359)
- [TH] Another NCCU/NCU thesis: of three risk measures and several windows, **idiosyncratic risk estimated over one month** best captures Taiwan's low-vol anomaly, making it a short-horizon strategy. — [NCU repository](https://ir.lib.ncu.edu.tw/handle/987654321/72962)
- [TH] NTU thesis, TWSE-listed stocks **1999-2021**: among lottery-like stocks, higher risk (monthly return std, idiosyncratic risk) goes with significantly lower average returns in regressions, though double-sort results are not significant for every risk measure. — [NTU thesis PDF](https://tdr.lib.ntu.edu.tw/bitstream/123456789/85398/1/U0001-1507202201150700.pdf)
- [PR, abstract only] Wang & Lien (2022, *RQFA*): a Taiwan "modified MAX" effect — stocks with high limit-up hit rates subsequently earn lower returns (unless the hits are revenue-news driven). — [Springer](https://link.springer.com/10.1007/s11156-022-01051-1)

### Inferences
- For a long-only swing book, the most defensible use of these slower factors is as **filters**, not as the timing signal: exclude the highest idiosyncratic-volatility / lottery-like names (repeated limit-ups without fundamental news), and require minimum profitability (e.g. positive ROE / operating margin) — both directions are supported by multiple Taiwan theses and one journal paper.
- The low-vol anomaly and the "remove extreme absolute strength stocks" momentum fix (section 1) are the same practical instruction viewed from two literatures: avoid the most volatile recent rockets.
- Value premia living in small caps means a liquidity-screened retail universe will capture less of it than headline numbers suggest.
- The reversed investment effect (high investment -> higher returns) is plausibly a capex-cycle feature of a tech-heavy market; do not import the US "conservative investment" tilt.

### Gaps
- **Short-term (1-week / 1-month) reversal in Taiwan**: no source found. This matters for the 2-week end of the holding range and remains unanswered.
- No peer-reviewed, full-text Taiwan factor premia (monthly %, t-stats) for value, profitability, size or low-vol; all of the above are thesis abstracts.
- No AQR / MSCI / Robeco Asia ex-Japan or EM factor notes were retrieved within the search budget.

---

## 6. Post-earnings-announcement drift (PEAD) in Taiwan

### Takeaway
PEAD exists in Taiwan and is seasonal and conditional (stronger near the 52-week high and in low-foreign-ownership stocks), but monthly revenue disclosure pre-empts much of the quarterly earnings news, so the cleaner drift to trade is the post-monthly-revenue drift described in section 3.

### Cited Findings
- [PR, abstract only] Fu (2014, *International Journal of Financial Research* 5(1):71-80), Taiwan earnings momentum: a **pronounced seasonal pattern** in post-announcement cumulative returns of hedge portfolios long positive / short negative earnings surprises; third-quarter results are weaker than first-quarter results. — [IDEAS](https://ideas.repec.org/a/jfr/ijfr11/v5y2014i1p71-80.html)
- [PR, abstract only] Lu (2019, *Journal of Applied Finance & Banking* 9(4)): tests whether unexpected operating vs non-operating income components each contribute to PEAD in Taiwan. Findings not read. — [IDEAS](https://ideas.repec.org/a/spt/apfiba/v9y2019i4f9_4_7.html)
- [PR (Taiwan journal), abstract only] FCU *Journal of Economics and Management* 17(1), TWSE non-financial stocks **2008Q1-2019Q2**: PEAD is related to 52-week-high anchoring and is stronger for stocks with low foreign ownership and high director ownership. — [JEM abstract](https://jem.fcu.edu.tw/assets/jem/past_issues/vol.17_no.1/Abstract/vol.17_no.1_01_Abstract.html)
- [PR, abstract only] Chen & Yu (2022): the drift associated with monthly revenue surprises **disappears at the quarterly earnings announcement** — information is already in the price. — [IDEAS](https://ideas.repec.org/a/kap/rqfnac/v58y2022i1d10.1007_s11156-021-00994-1.html)
- [PR, abstract only] 2024 *International Journal of Accounting* paper: monthly sales disclosures weaken earnings-announcement returns and PEAD when earnings are reported late. — [IDEAS](https://ideas.repec.org/a/wsi/tijaxx/v59y2024i01ns1094406024500021.html)
- [PR, search summary] Ku (2011) reports significant earnings momentum alongside revenue momentum in Taiwan (cited within Wang & Lien 2022). — [Springer](https://link.springer.com/10.1007/s11156-022-01051-1)

### Inferences
- Quarterly earnings surprises add most where monthly revenue cannot reveal them: margin changes and non-operating items. A rule could require positive revenue surprise AND improving gross/operating margin at the latest quarterly report.
- PEAD rules should be tested by quarter separately given the documented seasonality (Q1 stronger than Q3).
- Smaller, low-foreign-ownership stocks show more drift, which coincides with higher trading costs and lower liquidity — net edge is uncertain.

### Gaps
- No Taiwan PEAD effect size (CAR %, horizon in days, t-stat) was visible.
- No net-of-cost or long-only PEAD result found.

---

## 7. Factor combinations and realistic net-of-cost expectations for long-only

### Takeaway
No peer-reviewed Taiwan study that I could read reports a long-only, net-of-cost, top-quintile or top-decile multi-factor portfolio against TAIEX total return or 0050. The combination with the best-documented ingredients is revenue surprise/new-high + (conditional, volatility-screened) price strength or nearness to 52-week high + a quality/low-lottery filter + optional 投信 buying confirmation; the only outperformance numbers for such combinations are vendor backtests (roughly 24-44% annualized vs 12-18% for the index), which should be heavily discounted.

### Cited Findings
- [V] TEJ VAM top-10 mid-cap momentum, **net of fees/tax/slippage model, Dec 2019 - Dec 2024**: 43.84% annualized vs 18.43% TAIEX, max drawdown -34.55% vs -28.55%, underperformed the index in 2024 (+24.17% vs +31.73%) and lost 22.80% in 2022. — [TEJ via LINE TODAY](https://today.line.me/tw/v3/article/eL5pGnB)
- [V] cnyes: monthly revenue growth + moving-average uptrend, top 5, monthly rebalance, 10-year: 33.92%/yr vs 12.65% market. — [cnyes](https://hao.cnyes.com/post/9356)
- [V] cnyes: revenue 4-year high + institutional buying, 10-year: 23.57%/yr vs 12.59% index. — [cnyes](https://hao.cnyes.com/post/6318)
- [TH] NCCU 2010-2025 52-factor study: value and quality most stable; ML combination 15.90% annualized, Sharpe 2.50, **costs excluded**. — [NCCU thesis](https://thesis.lib.nccu.edu.tw/thesis/detail/cf3746d1cb1f3395292698a356f29edd)
- [TH] NCCU 2017 thesis: long-only size + B/M + profitability multi-factor portfolio beat single factors with significant excess returns. — [NDLTD record](https://openaccess.library.uitm.edu.my/Record/ndltd-TW-106NCCU5305034/Details)
- [PR] Ku (2010): revenue momentum is distinct from price and earnings momentum (survives controls), which is the academic basis for combining them. — [月旦知識庫 record](https://lawdata.com.tw/tw/detail.aspx?no=246130)
- [PR] Barber et al. (2009): after commissions and transaction tax, institutions gain 1.5 pp/yr and individuals lose 3.8 pp/yr — a base rate for how costly active retail trading is in Taiwan. — [Barber et al. 2009 PDF](https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/justhowmuchdoindividualinvestorslose_rfs_2009.pdf)

### Inferences
- **Cost arithmetic** (from the assignment's cost inputs): at ~0.585% per round trip before slippage, a monthly full-turnover portfolio pays about 7% per year; a 2-week full-turnover portfolio about 15% per year; a 3-month hold about 2.3% per year. With slippage in small/mid caps (0.6-0.9% round trip), 7-11% per year for monthly turnover. Any signal whose gross long-only edge over the index is below these figures is not worth trading at that frequency. This strongly favours the 1-3 month end of the user's holding range and signals with multi-month drift (revenue momentum: 1-12 months; institutional profits asymptote at ~6 months).
- **Proposed rule set to backtest, ranked by strength of Taiwan evidence**:
  1. Regime gate: only open new longs when the market is in an up state and not immediately after a state flip (Du 2009; Lin 2016; Sun 2011). Evidence: peer-reviewed, direction clear, thresholds unspecified.
  2. Fundamental trigger: positive monthly revenue surprise (SUR top quintile) or revenue at multi-year high, preferably the 2nd+ consecutive positive surprise; enter after the actual announcement date; hold until the next quarterly earnings date or up to ~3 months (Ku 2010; Chen & Yu 2022; Shen 2015).
  3. Price confirmation: price near 52-week high and/or volatility-adjusted relative strength; exclude extreme absolute-return outliers and stocks with repeated non-news limit-ups (Hao 2016; Lin 2020; Wang & Lien 2022).
  4. Quality/risk filter: positive profitability; drop top idiosyncratic-volatility quintile (theses).
  5. Flow confirmation (optional, weakest evidence): recent 投信 net buying for small/mid caps, with a time-stop of ~15-20 trading days on the flow thesis; high/rising margin utilisation as a negative filter (untested inference).
  6. Seasonality check: test with and without positions straddling January for the 52-week-high leg.
- **Realistic expectation**: there is no trustworthy published number. Vendor backtests showing 10-25 percentage points per year over the index come from 5-10 stock portfolios, 2010-2024 bull-heavy samples, with selection and look-ahead risks, and the one with a disclosed drawdown lost more than the index in drawdowns and lagged in 2024. A cautious prior is that a diversified (20-30 name) long-only version, net of real costs, would deliver a small fraction of those excess returns with index-like or worse drawdowns, and the regime gate matters more than stock ranking for drawdown control. This is my judgment, not a sourced figure; it must be established by the user's own point-in-time backtest against 0050 total return.
- Post-publication decay is a live risk for every signal here: revenue momentum (published 2010), 52-week high (2016), and institutional-flow screens are all standard features of Taiwan retail platforms.

### Gaps
- No peer-reviewed long-only, net-of-cost, top-quintile/decile Taiwan multi-factor result vs TAIEX TR / 0050 exists in what I could find; this is the key unanswered quantity.
- FinLab write-ups, TWSE/TAIFEX research reports on factors, and AQR/MSCI/Robeco regional notes were not retrieved.
- Most peer-reviewed sources (Pacific-Basin Finance Journal, IREF, RQFA, 管理學報) were readable only as abstracts; a follow-up with library access should extract the monthly returns and t-stats for: Hao et al. (2016), Lin et al. (2016, 2020), Chen/Hsieh/Lee (2023), Ku (2010), Chen & Yu (2022).
