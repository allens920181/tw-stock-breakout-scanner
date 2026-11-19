"""樣式注入的回歸測試：CSS 若在 Markdown 裡被切斷，整段樣式會變成畫面上的文字。"""
from twscanner.ui.format import fmt_money, fmt_pct, fmt_r, fmt_yi, rgba, stock_label
from twscanner.ui.theme import CSS, _html_block


def test_css_block_survives_markdown():
    html = _html_block(CSS)
    head, _, style = html.partition("<style>")
    assert head.endswith("\n\n")              # <link> 區塊要用空行結束
    assert "\n\n" not in style                 # <style> 內不能有空行
    assert style.rstrip().endswith("</style>")


def test_number_formats():
    assert fmt_pct(7.689) == "+7.69%" and fmt_pct(-1.01) == "−1.01%" and fmt_pct(None) == "—"
    assert fmt_money(372000, signed=True) == "+372,000 元" and fmt_money(-243) == "−243 元"
    assert fmt_yi(-243.14) == "−243.1 億" and fmt_r(1.349) == "+1.35R"
    assert stock_label("2330.TW", "台積電") == "2330 台積電" and stock_label("0050.TW", float("nan")) == "0050"
    assert rgba("#D7263D", 0.12) == "rgba(215, 38, 61, 0.12)"


def test_strip_icon_keeps_chinese():
    from twscanner.ui.format import strip_icon
    assert strip_icon("✅ 續抱") == "續抱"
    assert strip_icon("🟢 達 +1R 半倉鎖利") == "達 +1R 半倉鎖利"
    assert strip_icon("⚠ 續抱·留意減碼") == "續抱·留意減碼"
