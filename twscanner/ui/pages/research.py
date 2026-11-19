"""策略驗證：這套策略可信嗎？回測（含壓力測試、自動校準）+ 實戰績效與掃描歷史。"""
import streamlit as st

from twscanner.ui.pages import backtest, history


def render(sb):
    t_bt, t_live = st.tabs(["回測與校準", "實戰績效與歷史"])
    with t_bt:
        backtest.render(sb)
    with t_live:
        history.render()
