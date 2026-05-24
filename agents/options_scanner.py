# agents/options_scanner.py

import yfinance as yf
import pandas as pd
from datetime import datetime


def get_dte(expiration):
    today = datetime.now().date()
    exp_date = datetime.strptime(expiration, "%Y-%m-%d").date()
    return (exp_date - today).days


def scan_options(symbol="NVDA", max_rows=20, min_dte=30):
    symbol = symbol.upper()

    ticker = yf.Ticker(symbol)
    expirations = ticker.options

    if not expirations:
        return pd.DataFrame()

    valid_expirations = []

    for exp in expirations:
        dte = get_dte(exp)
        if dte >= min_dte:
            valid_expirations.append(exp)

    if not valid_expirations:
        return pd.DataFrame()

    all_contracts = []

    for expiration in valid_expirations[:4]:
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
    ]

    df = df[[col for col in needed_columns if col in df.columns]]

    for col in ["volume", "openInterest", "bid", "ask", "lastPrice", "impliedVolatility"]:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    df["premium"] = df["ask"]
    df.loc[df["premium"] <= 0, "premium"] = df["lastPrice"]

    df["spread"] = (df["ask"] - df["bid"]).round(2)

    df["spread_percent"] = 0.0
    df.loc[df["premium"] > 0, "spread_percent"] = (
        (df["spread"] / df["premium"]) * 100
    ).round(2)

    df["liquidity_score"] = (
        (df["volume"] * 0.45) +
        (df["openInterest"] * 0.55)
    )

    df["swing_score"] = 0

    df.loc[df["openInterest"] >= 1000, "swing_score"] += 25
    df.loc[df["openInterest"] >= 3000, "swing_score"] += 15

    df.loc[df["volume"] >= 300, "swing_score"] += 20
    df.loc[df["volume"] >= 1000, "swing_score"] += 15

    df.loc[df["dte"] >= 30, "swing_score"] += 10
    df.loc[df["dte"] >= 60, "swing_score"] += 10
    df.loc[df["dte"] >= 120, "swing_score"] += 10

    df.loc[(df["spread_percent"] > 0) & (df["spread_percent"] <= 20), "swing_score"] += 15
    df.loc[(df["spread_percent"] > 20) & (df["spread_percent"] <= 35), "swing_score"] += 8

    df.loc[(df["premium"] >= 0.50) & (df["premium"] <= 20), "swing_score"] += 10

    df["score"] = df["swing_score"].clip(upper=100)

    ratings = []

    for score in df["score"]:
        if score >= 85:
            ratings.append("🥇 MEJOR CONTRATO")
        elif score >= 70:
            ratings.append("🔥 FUERTE")
        elif score >= 55:
            ratings.append("👀 INTERESANTE")
        else:
            ratings.append("⚠️ BAJA PRIORIDAD")

    df["rating"] = ratings

    recommendations = []

    for _, row in df.iterrows():
        option_type = row.get("type", "")
        score = row.get("score", 0)

        if score >= 85:
            action = f"ENTRADA PRIORITARIA {option_type}"
        elif score >= 70:
            action = f"SWING FUERTE {option_type}"
        elif score >= 55:
            action = f"OBSERVAR SWING {option_type}"
        else:
            action = "NO PRIORITARIO"

        recommendations.append(action)

    df["recommendation"] = recommendations

    df["entry"] = df["premium"].round(2)
    df["take_profit"] = (df["premium"] * 1.50).round(2)
    df["stop_loss"] = (df["premium"] * 0.70).round(2)

    df = df.sort_values(
        by=["score", "liquidity_score"],
        ascending=False
    ).head(max_rows)

    return df