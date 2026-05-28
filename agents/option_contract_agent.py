# agents/option_contract_agent.py

import yfinance as yf
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo


NY_TIMEZONE = ZoneInfo("America/New_York")

MIN_DTE = 30
MAX_DTE = 120

MIN_VOLUME = 100
MIN_OPEN_INTEREST = 500
MAX_SPREAD_PCT = 12

OPTION_MULTIPLIER = 100

MAX_RISK_PER_TRADE = 400
MAX_ENTRY_PRICE = 15.00

MIN_DELTA = 0.70


def now_new_york():
    return datetime.now(NY_TIMEZONE)


def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def get_dte(expiration_date):
    try:
        exp = datetime.strptime(expiration_date, "%Y-%m-%d").replace(tzinfo=NY_TIMEZONE)
        today = now_new_york()
        return max((exp.date() - today.date()).days, 0)
    except Exception:
        return 0


def estimate_delta(option_type, strike, price):
    strike = safe_float(strike)
    price = safe_float(price)

    if price <= 0 or strike <= 0:
        return 0.0

    moneyness = strike / price

    if option_type == "CALL":
        if moneyness <= 0.88:
            return 0.90
        elif moneyness <= 0.92:
            return 0.85
        elif moneyness <= 0.96:
            return 0.75
        elif moneyness <= 1.00:
            return 0.65
        elif moneyness <= 1.05:
            return 0.45
        return 0.25

    if option_type == "PUT":
        if moneyness >= 1.12:
            return -0.90
        elif moneyness >= 1.08:
            return -0.85
        elif moneyness >= 1.04:
            return -0.75
        elif moneyness >= 1.00:
            return -0.65
        elif moneyness >= 0.95:
            return -0.45
        return -0.25

    return 0.0


def score_contract(row, price, option_type):
    strike = safe_float(row.get("strike"))
    last_price = safe_float(row.get("lastPrice"))
    bid = safe_float(row.get("bid"))
    ask = safe_float(row.get("ask"))
    volume = safe_float(row.get("volume"))
    open_interest = safe_float(row.get("openInterest"))
    dte = safe_float(row.get("dte"))

    if ask > 0 and bid > 0:
        mid_price = round((bid + ask) / 2, 2)
        spread = round(ask - bid, 2)
        spread_pct = round((spread / mid_price) * 100, 2) if mid_price > 0 else 100
    else:
        mid_price = last_price
        spread = 0
        spread_pct = 100

    delta = estimate_delta(option_type, strike, price)

    entry_price = mid_price if mid_price > 0 else last_price
    stop_loss = round(entry_price * 0.75, 2)
    take_profit = round(entry_price * 1.70, 2)

    risk_amount = round((entry_price - stop_loss) * OPTION_MULTIPLIER, 2)
    potential_profit = round((take_profit - entry_price) * OPTION_MULTIPLIER, 2)
    risk_reward = round(potential_profit / risk_amount, 2) if risk_amount > 0 else 0

    liquidity_score = min((volume / 1000) * 25, 25) + min((open_interest / 3000) * 25, 25)

    if spread_pct <= 3:
        spread_score = 25
    elif spread_pct <= 6:
        spread_score = 18
    elif spread_pct <= 9:
        spread_score = 12
    elif spread_pct <= MAX_SPREAD_PCT:
        spread_score = 6
    else:
        spread_score = 0

    if 45 <= dte <= 90:
        dte_score = 20
    elif MIN_DTE <= dte <= MAX_DTE:
        dte_score = 12
    else:
        dte_score = 0

    distance = abs((strike - price) / price) * 100 if price > 0 else 100

    if distance <= 5:
        moneyness_score = 15
    elif distance <= 10:
        moneyness_score = 12
    elif distance <= 20:
        moneyness_score = 8
    else:
        moneyness_score = 4

    delta_score = 20 if abs(delta) >= MIN_DELTA else 0
    price_score = 15 if entry_price <= MAX_ENTRY_PRICE else 0
    risk_score = 20 if risk_amount <= MAX_RISK_PER_TRADE else 0

    final_score = (
        liquidity_score
        + spread_score
        + dte_score
        + moneyness_score
        + delta_score
        + price_score
        + risk_score
    )

    final_score = round(min(final_score, 100), 2)

    return {
        "mid_price": entry_price,
        "spread": spread,
        "spread_pct": spread_pct,
        "delta_estimate": delta,
        "delta": delta,
        "entry_price": round(entry_price, 2),
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_amount": risk_amount,
        "potential_profit": potential_profit,
        "risk_reward": risk_reward,
        "liquidity_score": round(liquidity_score, 2),
        "spread_score": spread_score,
        "dte_score": dte_score,
        "moneyness_score": moneyness_score,
        "delta_score": delta_score,
        "price_score": price_score,
        "risk_score": risk_score,
        "contract_quality_score": final_score,
    }


def get_option_candidates(symbol, option_type="CALL", min_dte=MIN_DTE, max_dte=MAX_DTE):
    ticker = yf.Ticker(symbol)
    history = ticker.history(period="5d")

    if history.empty:
        return pd.DataFrame()

    price = safe_float(history["Close"].iloc[-1])
    expirations = ticker.options

    if not expirations:
        return pd.DataFrame()

    all_contracts = []

    for expiration in expirations:
        dte = get_dte(expiration)

        if dte < min_dte or dte > max_dte:
            continue

        try:
            chain = ticker.option_chain(expiration)
            df = chain.calls.copy() if option_type == "CALL" else chain.puts.copy()

            if df.empty:
                continue

            df["symbol"] = symbol
            df["option_type"] = option_type
            df["expiration"] = expiration
            df["dte"] = dte
            df["underlying_price"] = price

            all_contracts.append(df)

        except Exception:
            continue

    if not all_contracts:
        return pd.DataFrame()

    contracts = pd.concat(all_contracts, ignore_index=True)

    for col in ["volume", "openInterest", "bid", "ask", "lastPrice"]:
        contracts[col] = contracts[col].fillna(0)

    enriched_rows = []

    for _, row in contracts.iterrows():
        score_data = score_contract(row, price, option_type)

        for key, value in score_data.items():
            row[key] = value

        enriched_rows.append(row)

    contracts = pd.DataFrame(enriched_rows)

    contracts = contracts[
        (contracts["lastPrice"] > 0)
        & (contracts["volume"] >= MIN_VOLUME)
        & (contracts["openInterest"] >= MIN_OPEN_INTEREST)
        & (contracts["spread_pct"] <= MAX_SPREAD_PCT)
        & (contracts["entry_price"] <= MAX_ENTRY_PRICE)
        & (contracts["risk_amount"] <= MAX_RISK_PER_TRADE)
        & (contracts["delta_estimate"].abs() >= MIN_DELTA)
    ]

    if contracts.empty:
        return pd.DataFrame()

    contracts = contracts.sort_values(
        by=[
            "contract_quality_score",
            "delta_score",
            "risk_reward",
            "openInterest",
            "volume",
        ],
        ascending=False,
    )

    return contracts


def select_best_option_contract(symbol, direction="CALL"):
    option_type = "CALL" if direction.upper() in ["CALL", "BUY CALL", "UP", "BULLISH"] else "PUT"

    candidates = get_option_candidates(symbol, option_type=option_type)

    if candidates.empty:
        return None

    return candidates.iloc[0].to_dict()


def option_contract_agent(state):
    symbol = state.get("symbol")
    strategy = state.get("strategy", "")
    trend = state.get("trend", "")
    signal = state.get("signal", "")
    entry_type = state.get("entry_type", "")

    state["analysis_datetime_ny"] = now_new_york().strftime("%Y-%m-%d %I:%M:%S %p New York")

    if not symbol:
        state["best_contract"] = None
        state["contract_status"] = "No symbol provided."
        return state

    direction = "CALL"
    text = f"{strategy} {trend} {signal} {entry_type}".upper()

    if "PUT" in text or "DOWN" in text or "BEARISH" in text or "SELL" in text:
        direction = "PUT"
    elif "CALL" in text or "UP" in text or "BULLISH" in text or "BUY" in text:
        direction = "CALL"

    try:
        best_contract = select_best_option_contract(symbol, direction)

        if best_contract is None:
            state["best_contract"] = None
            state["contract_status"] = (
                f"No contract found. Requirements: "
                f"min delta {MIN_DELTA}, "
                f"max risk ${MAX_RISK_PER_TRADE}, "
                f"max entry price ${MAX_ENTRY_PRICE}, "
                f"min volume {MIN_VOLUME}, "
                f"min open interest {MIN_OPEN_INTEREST}, "
                f"max spread {MAX_SPREAD_PCT}%."
            )
            return state

        state["best_contract"] = best_contract
        state["contract_status"] = "Contract selected successfully."

        fields = [
            "contractSymbol",
            "option_type",
            "expiration",
            "dte",
            "strike",
            "underlying_price",
            "lastPrice",
            "bid",
            "ask",
            "mid_price",
            "spread",
            "spread_pct",
            "volume",
            "openInterest",
            "delta_estimate",
            "delta",
            "contract_quality_score",
            "liquidity_score",
            "spread_score",
            "dte_score",
            "moneyness_score",
            "delta_score",
            "price_score",
            "risk_score",
            "entry_price",
            "stop_loss",
            "take_profit",
            "risk_amount",
            "potential_profit",
            "risk_reward",
        ]

        for field in fields:
            state[field] = best_contract.get(field)

        state["option_contract"] = best_contract.get("contractSymbol")

        if not state.get("contracts"):
            state["contracts"] = 1

        return state

    except Exception as e:
        state["best_contract"] = None
        state["contract_status"] = f"Error selecting contract: {e}"
        return state