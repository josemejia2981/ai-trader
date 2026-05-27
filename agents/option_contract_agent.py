# agents/option_contract_agent.py

import yfinance as yf
import pandas as pd
from datetime import datetime


MIN_DTE = 30
MAX_DTE = 120

MIN_VOLUME = 10
MIN_OPEN_INTEREST = 50
MAX_SPREAD_PCT = 25

OPTION_MULTIPLIER = 100

MAX_RISK_PER_TRADE = 200
MAX_ENTRY_PRICE = 6.00


def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def get_dte(expiration_date):
    try:
        exp = datetime.strptime(expiration_date, "%Y-%m-%d")
        today = datetime.now()
        return max((exp - today).days, 0)
    except Exception:
        return 0


def estimate_delta(option_type, strike, price):
    strike = safe_float(strike)
    price = safe_float(price)

    if price <= 0 or strike <= 0:
        return 0.50

    moneyness = strike / price

    if option_type == "CALL":
        if moneyness <= 0.95:
            return 0.70
        elif moneyness <= 1.03:
            return 0.55
        elif moneyness <= 1.10:
            return 0.40
        else:
            return 0.25

    if option_type == "PUT":
        if moneyness >= 1.05:
            return 0.70
        elif moneyness >= 0.97:
            return 0.55
        elif moneyness >= 0.90:
            return 0.40
        else:
            return 0.25

    return 0.50


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
    stop_loss = round(entry_price * 0.65, 2)
    take_profit = round(entry_price * 1.80, 2)

    risk_amount = round((entry_price - stop_loss) * OPTION_MULTIPLIER, 2)
    potential_profit = round((take_profit - entry_price) * OPTION_MULTIPLIER, 2)
    risk_reward = round(potential_profit / risk_amount, 2) if risk_amount > 0 else 0

    liquidity_score = min((volume / 500) * 25, 25) + min((open_interest / 1000) * 25, 25)

    if spread_pct <= 5:
        spread_score = 25
    elif spread_pct <= 10:
        spread_score = 18
    elif spread_pct <= 15:
        spread_score = 10
    elif spread_pct <= 25:
        spread_score = 5
    else:
        spread_score = 0

    if 35 <= dte <= 75:
        dte_score = 20
    elif 30 <= dte <= 120:
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

    delta_score = 15 if 0.25 <= delta <= 0.70 else 5

    price_score = 15 if entry_price <= MAX_ENTRY_PRICE else 0
    risk_score = 20 if risk_amount <= MAX_RISK_PER_TRADE else 0

    final_score = (
        liquidity_score +
        spread_score +
        dte_score +
        moneyness_score +
        delta_score +
        price_score +
        risk_score
    )

    final_score = round(min(final_score, 100), 2)

    return {
        "mid_price": entry_price,
        "spread": spread,
        "spread_pct": spread_pct,
        "delta_estimate": delta,
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

            if option_type == "CALL":
                df = chain.calls.copy()
            else:
                df = chain.puts.copy()

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

    contracts["volume"] = contracts["volume"].fillna(0)
    contracts["openInterest"] = contracts["openInterest"].fillna(0)
    contracts["bid"] = contracts["bid"].fillna(0)
    contracts["ask"] = contracts["ask"].fillna(0)
    contracts["lastPrice"] = contracts["lastPrice"].fillna(0)

    enriched_rows = []

    for _, row in contracts.iterrows():
        score_data = score_contract(row, price, option_type)

        for key, value in score_data.items():
            row[key] = value

        enriched_rows.append(row)

    contracts = pd.DataFrame(enriched_rows)

    contracts = contracts[
        (contracts["lastPrice"] > 0) &
        (contracts["volume"] >= MIN_VOLUME) &
        (contracts["openInterest"] >= MIN_OPEN_INTEREST) &
        (contracts["spread_pct"] <= MAX_SPREAD_PCT) &
        (contracts["entry_price"] <= MAX_ENTRY_PRICE) &
        (contracts["risk_amount"] <= MAX_RISK_PER_TRADE)
    ]

    if contracts.empty:
        return pd.DataFrame()

    contracts = contracts.sort_values(
        by=[
            "contract_quality_score",
            "risk_reward",
            "openInterest",
            "volume"
        ],
        ascending=False
    )

    return contracts


def select_best_option_contract(symbol, direction="CALL"):
    option_type = "CALL" if direction.upper() in ["CALL", "BUY CALL", "UP", "BULLISH"] else "PUT"

    candidates = get_option_candidates(symbol, option_type=option_type)

    if candidates.empty:
        return None

    best = candidates.iloc[0].to_dict()

    return best


def option_contract_agent(state):
    symbol = state.get("symbol")
    strategy = state.get("strategy", "")
    trend = state.get("trend", "")
    signal = state.get("signal", "")
    entry_type = state.get("entry_type", "")

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
                f"No contract found under risk limit. "
                f"Max risk allowed: ${MAX_RISK_PER_TRADE}, "
                f"max entry price: ${MAX_ENTRY_PRICE}"
            )
            return state

        state["best_contract"] = best_contract
        state["contract_status"] = "Contract selected successfully."

        state["contractSymbol"] = best_contract.get("contractSymbol")
        state["option_contract"] = best_contract.get("contractSymbol")
        state["option_type"] = best_contract.get("option_type")
        state["expiration"] = best_contract.get("expiration")
        state["dte"] = best_contract.get("dte")
        state["strike"] = best_contract.get("strike")
        state["underlying_price"] = best_contract.get("underlying_price")

        state["lastPrice"] = best_contract.get("lastPrice")
        state["bid"] = best_contract.get("bid")
        state["ask"] = best_contract.get("ask")
        state["mid_price"] = best_contract.get("mid_price")
        state["spread"] = best_contract.get("spread")
        state["spread_pct"] = best_contract.get("spread_pct")
        state["volume"] = best_contract.get("volume")
        state["openInterest"] = best_contract.get("openInterest")
        state["delta_estimate"] = best_contract.get("delta_estimate")

        state["contract_quality_score"] = best_contract.get("contract_quality_score")
        state["liquidity_score"] = best_contract.get("liquidity_score")
        state["spread_score"] = best_contract.get("spread_score")
        state["dte_score"] = best_contract.get("dte_score")
        state["moneyness_score"] = best_contract.get("moneyness_score")
        state["price_score"] = best_contract.get("price_score")
        state["risk_score"] = best_contract.get("risk_score")

        state["entry_price"] = best_contract.get("entry_price")
        state["stop_loss"] = best_contract.get("stop_loss")
        state["take_profit"] = best_contract.get("take_profit")
        state["risk_amount"] = best_contract.get("risk_amount")
        state["potential_profit"] = best_contract.get("potential_profit")
        state["risk_reward"] = best_contract.get("risk_reward")

        if not state.get("contracts"):
            state["contracts"] = 1

        return state

    except Exception as e:
        state["best_contract"] = None
        state["contract_status"] = f"Error selecting contract: {e}"
        return state