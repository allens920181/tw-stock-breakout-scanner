"""
台股強勢突破掃描器 — Streamlit 入口（Streamlit Cloud 的 Main file path 指向此檔）

    uv run streamlit run app.py

實作都在 twscanner/ui/，此檔只負責啟動。
"""
from twscanner.ui.app import main

main()
