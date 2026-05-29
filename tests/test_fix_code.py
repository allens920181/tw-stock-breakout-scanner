import pandas as pd
import pytest

from src.fetcher import fix_stock_code


ETF_MAP = {
    "9805": "009805",
    "899": "00899",
    "920": "00920",
}


@pytest.mark.parametrize("inp,expected", [
    ("2330", "2330"),
    ("2330.0", "2330"),
    (" 2330 ", "2330"),
    ("50", "0050"),       # 補零
    ("9805", "009805"),   # ETF map
    ("899", "00899"),     # ETF map
    ("", None),
    ("nan", None),
])
def test_fix_stock_code(inp, expected):
    assert fix_stock_code(inp, ETF_MAP) == expected


def test_fix_stock_code_nan():
    assert fix_stock_code(pd.NA, ETF_MAP) is None
    assert fix_stock_code(float("nan"), ETF_MAP) is None
