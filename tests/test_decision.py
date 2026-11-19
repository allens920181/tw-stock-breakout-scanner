"""今日決策相關的純計算：月目標、交易紀錄、組合風險、個股健檢、進場日推估、今日決策組裝。"""
import io

import numpy as np
import pandas as pd

from twscanner.analysis import goal, health
from twscanner.data.fundamentals import parse_balance, parse_eps, parse_ratios
from twscanner.portfolio import trade_log
from twscanner.portfolio.holdings import infer_entry_date
from twscanner.portfolio.risk import portfolio_risk
from twscanner.services.today import build_today, candidates, holding_actions, trade_plan

COSTS = {"fee_rate": 0.001425, "fee_discount": 1.0, "tax_rate": 0.003}


# ---------- 月目標 ----------
def test_trades_needed_and_negative_edge():
    assert goal.trades_needed(10_000, 1_000_000, 0.01, 0.25) == 4
    assert goal.trades_needed(10_000, 1_000_000, 0.01, -0.1) is None
    p = goal.plan(1_000_000, 0.01, 10_000, {"expectancy_r": -0.12, "n": 33})
    assert p["status"] == "negative" and "先別用真錢" in p["verdict"]
    assert p["loss_limit"] == 20_000


def test_plan_feasible_and_stretch():
    s = {"expectancy_r": 0.3, "win_rate": 0.4, "avg_win_r": 2.25, "avg_loss_r": 1.0, "n": 50}
    p = goal.plan(1_000_000, 0.01, 10_000, s)
    assert p["status"] == "feasible" and abs(p["trades_needed"] - 10 / 3) < 1e-9
    assert 0 < p["sim"]["p_loss"] < 1
    p2 = goal.plan(300_000, 0.01, 10_000, s)
    assert p2["status"] == "stretch"


def test_month_progress_stop_rule():
    pr = goal.month_progress(-21_000, -2.1, 10_000)
    assert pr["stop_trading"] and "停手" in pr["status"]
    pr = goal.month_progress(12_000, 1.2, 10_000, history=[-4_000, 8_000, 99])
    assert pr["avg3"] == (12_000 - 4_000 + 8_000) / 3 and not pr["stop_trading"]


def test_simulation_matches_expectancy():
    sim = goal.simulate_months(0.4, 2.2, 4, 10_000, 10_000, n=40_000)
    assert abs(sim["mean"] - 4 * 0.28 * 10_000) < 600


def test_stats_from_r():
    s = goal.stats_from_r([2.0, -1.0, -1.0, float("nan"), None, 3.0], "x")
    assert s["n"] == 4 and s["win_rate"] == 0.5 and abs(s["expectancy_r"] - 0.75) < 1e-9


# ---------- 交易紀錄 ----------
def test_trade_pnl_with_costs_and_r():
    res = trade_log.trade_pnl(100.0, 110.0, 1000, COSTS, stop=95.0)
    fees = 142 + 156 + 330          # 手續費雙邊（142.5、156.75 捨去）+ 證交稅
    assert res["pnl"] == 10_000 - fees
    assert abs(res["r_multiple"] - (10_000 - fees) / 5_000) < 1e-9
    small = trade_log.trade_pnl(10.0, 10.5, 100, COSTS)
    assert small["fees"] == 20 + 20 + 3   # 最低手續費 20 元


def test_monthly_summary_and_month_stats():
    df = pd.DataFrame([
        {"賣出日": "2026-11-05", "股票代號": "2330", "買進日": "2026-10-20", "買進價": 100, "賣出價": 110,
         "股數": 1000, "停損價": 95},
        {"賣出日": "2026-11-12", "股票代號": "2317", "買進日": "2026-11-01", "買進價": 50, "賣出價": 48,
         "股數": 2000, "停損價": 48},
        {"賣出日": "2026-10-03", "股票代號": "2603", "買進日": "2026-09-20", "買進價": 200, "賣出價": 210,
         "股數": 1000, "停損價": None},
    ])
    c = trade_log.compute(df, COSTS)
    assert c.loc[0, "持有天數"] == 16
    summ = trade_log.monthly_summary(c)
    assert list(summ["月份"]) == ["2026-11", "2026-10"]
    assert summ.loc[0, "筆數"] == 2 and summ.loc[0, "勝率%"] == 50
    realized, r_sum, prev = trade_log.month_stats(c, "2026-11")
    assert realized == c.loc[0, "損益(元)"] + c.loc[1, "損益(元)"]
    assert len(prev) == 1
    st = trade_log.stats_for_goal(c)
    assert st["n"] == 2                   # 第 3 筆沒停損價 → 沒有 R


# ---------- 組合風險 ----------
def test_portfolio_risk_rules():
    rows = [
        {"股票": "2330.TW", "目前價": 100, "停損價": 90, "持有股數": 3000},
        {"股票": "2317.TW", "目前價": 50, "停損價": 52, "持有股數": 1000},   # 已破停損
        {"股票": "2603.TW", "目前價": None, "停損價": 90, "持有股數": 1000},  # 沒資料略過
    ]
    r = portfolio_risk(rows, 500_000, max_risk_pct=5)
    assert r["total_risk"] == 30_000 and r["positions"] == 2
    assert r["risk_pct"] == 6 and not r["ok"]
    assert r["below_stop"] == ["2317"]


# ---------- 個股健檢 ----------
def test_health_report_flags_core_loss_and_valuation():
    fund = {"year": "115", "quarter": "3", "industry": "塑膠工業", "eps": 3.0,
            "op_income_k": -100.0, "net_income_k": 500.0, "revenue_k": 10_000.0,
            "gross_margin": 8.0, "assets_k": 1000.0, "liabilities_k": 700.0,
            "current_assets_k": 80.0, "current_liabilities_k": 100.0, "bvps": 50.0}
    rev = {"yoy_pct": -25.0, "mom_pct": 3.0, "month": "11510", "note": "需求疲弱"}
    rep = health.health_report(fund, rev, price=40.0)
    keys = {i["key"]: i for i in rep["items"]}
    assert keys["op_margin"]["verdict"] == "bad" and "業外" in keys["op_margin"]["plain"]
    assert keys["revenue"]["verdict"] == "bad" and "需求疲弱" in keys["revenue"]["plain"]
    assert abs(rep["valuation"]["pe"] - 40 / 4.0) < 1e-9          # 年化 EPS = 3 × 4/3
    assert keys["debt"]["verdict"] == "bad" and keys["current"]["verdict"] == "bad"
    assert "要注意" in rep["summary"] and rep["period"] == "2026 年前 3 季累計"


def test_health_report_financials_and_empty():
    fin = {"industry": "金融保險業", "assets_k": 100.0, "liabilities_k": 92.0}
    rep = health.health_report(fin)
    assert rep["items"][0]["verdict"] == "na"
    assert "查無財報" in health.health_report(None)["summary"]


def test_fundamentals_parsers():
    eps = parse_eps([{"公司代號": "2330", "年度": "115", "季別": "3", "基本每股盈餘(元)": "78.75",
                      "營業收入": "3,898,726,974.00", "營業利益": "", "稅後淨利": "1"}])
    assert eps["2330"]["eps"] == 78.75 and eps["2330"]["op_income_k"] is None
    rat = parse_ratios([{"公司代號": "2330", "毛利率(%)(營業毛利)/(營業收入)": "66.79"}])
    assert rat["2330"]["gross_margin"] == 66.79
    bal = parse_balance([{"公司代號": "2881", "資產總額": "100", "負債總額": "90", "每股參考淨值": "55"}])
    assert bal["2881"] == {"assets_k": 100.0, "liabilities_k": 90.0, "bvps": 55.0}


# ---------- 進場日推估（個股查詢與持股一致的關鍵）----------
def test_infer_entry_date():
    idx = pd.bdate_range("2026-09-01", periods=60)
    close = np.linspace(100, 160, 60)
    df = pd.DataFrame({"High": close + 1, "Low": close - 1, "Close": close}, index=idx)
    d, note = infer_entry_date(df, 130.0)
    assert d == idx[30].date() and "推估" in note
    d2, note2 = infer_entry_date(df, 50.0)        # 從未觸及 → 約一個月前
    assert d2 == idx[40].date() and "一個月" in note2


# ---------- 上傳持股：代號為數字也不能崩 ----------
def test_holdings_excel_codes_read_as_text():
    buf = io.BytesIO()
    pd.DataFrame({"股票代號": [2330, 50], "成本價": [1950, 150]}).to_excel(buf, index=False)
    buf.seek(0)
    df = pd.read_excel(buf, dtype={"股票代號": str})
    assert df["股票代號"].tolist() == ["2330", "50"]


# ---------- 今日決策 ----------
def _scan():
    base = {"市場": "TW", "評分": 7, "進場參考價": 100.0, "停損價": 95.0, "目標價1(+1R半倉)": 105.0,
            "目標價2(+2R出清)": 110.0, "建議張數": 2, "突破+量增": True, "MA多頭": True,
            "KD強勢": float("nan"), "籌碼確認": "法人連買3日", "綜合評級": "A"}
    return pd.DataFrame([
        {**base, "股票": "2330.TW", "公司名稱": "台積電", "訊號判斷": "進場"},
        {**base, "股票": "2317.TW", "公司名稱": "鴻海", "訊號判斷": "觀察", "評分": 9},
        {**base, "股票": "2603.TW", "公司名稱": "長榮", "訊號判斷": "不操作", "評分": 10},
    ])


def test_candidates_order_and_plan():
    c = candidates(_scan())
    assert [x["code"] for x in c] == ["2330", "2317"]      # 進場優先於分數高的觀察
    p = c[0]
    assert p["risk_amount"] == 5 * 2 * 1000
    assert "突破近 20 日高點且放量" in p["reasons"] and "KD 強勢" not in p["reasons"]
    assert "法人連買3日" in p["reasons"]
    assert trade_plan({"股票": "1101.TW"})["entry"] is None


def test_holding_actions_urgent_first():
    h = pd.DataFrame([
        {"股票": "2317.TW", "操作建議": "✅ 續抱", "賣出量": "保留"},
        {"股票": "2330.TW", "操作建議": "⛔ 停損出清", "賣出量": "全出"},
    ])
    a = holding_actions(h)
    assert a[0]["code"] == "2330" and a[0]["urgent"] and not a[1]["urgent"]


def test_build_today_gates():
    cfg = {"position_sizing": {"total_capital": 1_000_000, "risk_per_trade_pct": 0.01}}
    t = build_today({"regime": "bull"}, _scan(), None, None, cfg, "2026-11")
    assert t["can_open"] and "1 檔達進場標準" in t["headline"]
    t = build_today({"regime": "bear"}, _scan(), None, None, cfg, "2026-11")
    assert not t["can_open"] and "空頭" in t["reasons"][0]
    t = build_today({"regime": "bull"}, None, None, None, cfg, "2026-11")
    assert "還沒掃描" in t["headline"]
    t = build_today(None, _scan(), None, None, cfg, "2026-11")      # 大盤未知 → 不能說可以開倉
    assert not t["can_open"] and "大盤狀態" in t["reasons"][0]


def test_capital_for_target():
    from twscanner.analysis.goal import capital_for_target, plan
    assert capital_for_target(10_000, 0.08) == 1_500_000
    assert capital_for_target(10_000, 0) is None
    assert plan(1_000_000, 0.01, 10_000)["required_annual_pct"] == 12
