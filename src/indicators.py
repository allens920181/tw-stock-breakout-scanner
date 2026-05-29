import pandas as pd


def add_indicators(df):
    df = df.copy()
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()

    low = df["Low"].rolling(9).min()
    high = df["High"].rolling(9).max()
    rsv = (df["Close"] - low) / (high - low) * 100

    df["K"] = rsv.ewm(com=2).mean()
    df["D"] = df["K"].ewm(com=2).mean()

    ema12 = df["Close"].ewm(span=12).mean()
    ema26 = df["Close"].ewm(span=26).mean()

    df["DIF"] = ema12 - ema26
    df["MACD"] = df["DIF"].ewm(span=9).mean()
    df["OSC"] = df["DIF"] - df["MACD"]

    return df
