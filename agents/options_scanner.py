# agents/options_scanner.py

import os
from datetime import datetime

import pandas as pd
import yfinance as yf


def get_dte(expiration):
    today = datetime.now().date()
    exp_date = datetime.strptime(expiration, "%Y-%m-%d").date()
    return (exp_date - today).days


def scan_options(symbol="NVDA", max_rows=20, min_dte=30):
    symbol = symbol.upper()
    ticker = yf.Ticker(symbol)

    try:
        hist = ticker.history(period="5d")
        current_price = float(hist["Close"].iloc[-1]) if not hist.empty else 0
    except Exception:
        current_price = 0

    try:
        expirations = ticker.options
    except Exception:
        return pd.DataFrame()

    valid_expirations = [
        exp for exp in expirations
        if get_dte(exp) >= min_dte
    ]

    if not valid_expirations:
        return pd.DataFrame()

    all_contracts = []

    for expiration in valid_expirations[:5]:
        try:
            dte = get_dte(expiration)
            chain = ticker.option_chain(expiration)

            calls = chain.calls.copy()
            puts = chain.puts.copy()

            calls["type"] = "CALL"
            puts["type"] = "PUT"

            df = pd.concat([calls, puts], ignore_index=True)

            df["symbol"] = symbol
            df["expiration"] = expiration
            df["dte"] = dte
            df["current_price"] = current_price

            all_contracts.append(df)

        except Exception:
            continue

    if not all_contracts:
        return pd.DataFrame()

    df = pd.concat(all_contracts, ignore_index=True)

    needed_columns = [
        "contractSymbol",
        "symbol",
        "expiration",
        "dte",
        "type",
        "strike",
        "lastPrice",
        "bid",
        "ask",
        "volume",
        "openInterest",
        "impliedVolatility",
        "current_price",
    ]

    df = df[[col for col in needed_columns if col in df.columns]]

    for col in [
        "strike",
        "volume",
        "openInterest",
        "bid",
        "ask",
        "lastPrice",
        "impliedVolatility",
        "current_price",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["premium"] = df["ask"]
    df.loc[df["premium"] <= 0, "premium"] = df["lastPrice"]

    df = df[df["premium"] > 0]
    df = df[df["strike"] > 0]

    if df.empty:
        return pd.DataFrame()

    df["spread"] = (df["ask"] - df["bid"]).round(2)

    df["spread_percent"] = 0.0
    df.loc[df["premium"] > 0, "spread_percent"] = (
        (df["spread"] / df["premium"]) * 100
    ).round(2)

    df["moneyness_percent"] = 0.0
    if current_price > 0:
        df["moneyness_percent"] = (
            abs(df["strike"] - current_price) / current_price * 100
        ).round(2)

    df["score"] = 0

    df.loc[df["openInterest"] >= 500, "score"] += 8
    df.loc[df["openInterest"] >= 1000, "score"] += 7
    df.loc[df["openInterest"] >= 3000, "score"] += 5
    df.loc[df["volume"] >= 100, "score"] += 3
    df.loc[df["volume"] >= 300, "score"] += 2

    df.loc[(df["spread_percent"] > 0) & (df["spread_percent"] <= 10), "score"] += 20
    df.loc[(df["spread_percent"] > 10) & (df["spread_percent"] <= 20), "score"] += 15
    df.loc[(df["spread_percent"] > 20) & (df["spread_percent"] <= 35), "score"] += 8

    df.loc[(df["dte"] >= 45) & (df["dte"] <= 90), "score"] += 20
    df.loc[(df["dte"] >= 30) & (df["dte"] < 45), "score"] += 12
    df.loc[(df["dte"] > 90) & (df["dte"] <= 150), "score"] += 12
    df.loc[(df["dte"] > 150) & (df["dte"] <= 240), "score"] += 6

    df.loc[df["moneyness_percent"] <= 5, "score"] += 20
    df.loc[(df["moneyness_percent"] > 5) & (df["moneyness_percent"] <= 10), "score"] += 15
    df.loc[(df["moneyness_percent"] > 10) & (df["moneyness_percent"] <= 15), "score"] += 8
    df.loc[(df["moneyness_percent"] > 15) & (df["moneyness_percent"] <= 25), "score"] += 3

    df.loc[(df["premium"] >= 1) & (df["premium"] <= 15), "score"] += 15
    df.loc[(df["premium"] > 15) & (df["premium"] <= 30), "score"] += 8
    df.loc[(df["premium"] >= 0.50) & (df["premium"] < 1), "score"] += 5

    df["score"] = df["score"].clip(upper=100)
    df["swing_score"] = df["score"]

    df["liquidity_score"] = (
        (df["volume"] * 0.45) +
        (df["openInterest"] * 0.55)
    ).round(2)

    df["rating"] = df["score"].apply(get_rating)

    df["entry_price"] = df["premium"].round(2)
    df["stop_loss"] = (df["premium"] * 0.70).round(2)
    df["take_profit"] = (df["premium"] * 1.50).round(2)

    df = df.sort_values(
        by=["score", "openInterest", "volume"],
        ascending=False
    )

    return df.head(max_rows)


def get_rating(score):
    if score >= 90:
        return "EXCELENTE"
    elif score >= 80:
        return "MUY FUERTE"
    elif score >= 70:
        return "FUERTE"
    elif score >= 60:
        return "INTERESANTE"
    elif score >= 50:
        return "REGULAR"
    else:
        return "DEBIL"


def run_auto_options_scanner(results=None):
    print("Ejecutando scanner automatico de opciones...")

    symbols = []

    if results:
        for item in results:
            symbol = item.get("symbol")
            if symbol:
                symbols.append(symbol)

    if not symbols:
        symbols = ["NVDA", "AAPL", "TSLA", "MSFT"]

    all_results = []

    for symbol in symbols:
        print(f"Buscando mejores contratos para {symbol}...")

        try:
            df = scan_options(symbol=symbol, max_rows=5, min_dte=30)

            if df.empty:
                continue

            all_results.append(df)

        except Exception as e:
            print(f"Error escaneando {symbol}: {e}")

    if not all_results:
        print("No se encontraron contratos.")
        return None

    final_df = pd.concat(all_results, ignore_index=True)

    final_df = final_df.sort_values(
        by=["score", "openInterest", "volume"],
        ascending=False
    )

    os.makedirs("reports", exist_ok=True)

    filename = datetime.now().strftime("reports/options_scanner_%Y_%m_%d_%H_%M.csv")
    final_df.to_csv(filename, index=False)

    print(f"Reporte scanner guardado: {filename}")

    return filename


if __name__ == "__main__":
    report = run_auto_options_scanner()
    print(report)