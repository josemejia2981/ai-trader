# agents/option_contract_agent.py

import yfinance as yf
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo


NY_TIMEZONE = ZoneInfo("America/New_York")

MIN_DTE = 30
MAX_DTE = 120

MIN_VOLUME = 50
MIN_OPEN_INTEREST = 300
MAX_SPREAD_PCT = 12

OPTION_MULTIPLIER = 100

MAX_RISK_PER_TRADE = 650
MAX_ENTRY_PRICE = 25.00

MIN_DELTA = 0.65

MAX_CALL_OTM_PCT = 0.08
MAX_PUT_OTM_PCT = 0.08
MAX_STRIKE_DISTANCE_PCT = 0.12


def now_new_york():
    return datetime.now(NY_TIMEZONE)


def safe_float(value, default=0.0):
    try:
        if value is None or pd.isna(value):
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

    ratio = strike / price

    if option_type == "CALL":
        if ratio <= 0.90:
            return 0.85
        elif ratio <= 0.95:
            return 0.75
        elif ratio <= 1.00:
            return 0.65
        elif ratio <= 1.04:
            return 0.55
        elif ratio <= 1.08:
            return 0.45
        return 0.25

    if option_type == "PUT":
        if ratio >= 1.10:
            return -0.85
        elif ratio >= 1.05:
            return -0.75
        elif ratio >= 1.00:
            return -0.65
        elif ratio >= 0.96:
            return -0.55
        elif ratio >= 0.92:
            return -0.45
        return -0.25

    return 0.0


def is_strike_valid(option_type, strike, price):
    strike = safe_float(strike)
    price = safe_float(price)

    if strike <= 0 or price <= 0:
        return False

    distance_pct = abs(strike - price) / price

    if distance_pct > MAX_STRIKE_DISTANCE_PCT:
        return False

    if option_type == "CALL":
        if strike > price * (1 + MAX_CALL_OTM_PCT):
            return False

    if option_type == "PUT":
        if strike < price * (1 - MAX_PUT_OTM_PCT):
            return False

    return True


def build_action_levels(option_type, underlying_price, strike, entry_price):
    underlying_price = safe_float(underlying_price)
    strike = safe_float(strike)
    entry_price = safe_float(entry_price)

    if underlying_price <= 0:
        return {}

    if option_type == "CALL":
        stock_entry = round(underlying_price, 2)
        stock_stop = round(underlying_price * 0.97, 2)
        stock_tp1 = round(max(strike, underlying_price * 1.04), 2)
        stock_tp2 = round(underlying_price * 1.08, 2)
    else:
        stock_entry = round(underlying_price, 2)
        stock_stop = round(underlying_price * 1.03, 2)
        stock_tp1 = round(min(strike, underlying_price * 0.96), 2)
        stock_tp2 = round(underlying_price * 0.92, 2)

    option_stop = round(entry_price * 0.70, 2)
    option_tp1 = round(entry_price * 1.50, 2)
    option_tp2 = round(entry_price * 2.00, 2)
    max_option_entry = round(entry_price * 1.08, 2)
    trailing_stop = round(entry_price * 1.25, 2)

    return {
        "stock_entry_price": stock_entry,
        "stock_stop_loss": stock_stop,
        "stock_take_profit_1": stock_tp1,
        "stock_take_profit_2": stock_tp2,
        "max_option_entry": max_option_entry,
        "option_stop_loss": option_stop,
        "option_take_profit_1": option_tp1,
        "option_take_profit_2": option_tp2,
        "option_trailing_stop": trailing_stop,
    }


def get_recommendation(score, delta, risk_reward, spread_pct, volume, open_interest):
    score = safe_float(score)
    delta = abs(safe_float(delta))
    risk_reward = safe_float(risk_reward)
    spread_pct = safe_float(spread_pct)
    volume = safe_float(volume)
    open_interest = safe_float(open_interest)

    if (
        score >= 85
        and delta >= 0.65
        and risk_reward >= 2
        and spread_pct <= 8
        and volume >= 100
        and open_interest >= 1000
    ):
        return "🔥 ALTO RENDIMIENTO", "Contrato fuerte: delta, liquidez, spread y riesgo/recompensa favorables."

    if score >= 75 and delta >= 0.65 and risk_reward >= 1.8:
        return "✅ BUENA OPORTUNIDAD", "Contrato válido con estructura operable."

    if score >= 60:
        return "👀 WATCHLIST", "Contrato aceptable, pero necesita mejor confirmación."

    return "🔴 EVITAR", "Contrato débil o con condiciones insuficientes."


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

    entry_price = mid_price if mid_price > 0 else last_price
    delta = estimate_delta(option_type, strike, price)

    levels = build_action_levels(option_type, price, strike, entry_price)

    option_stop = levels.get("option_stop_loss", round(entry_price * 0.70, 2))
    option_tp1 = levels.get("option_take_profit_1", round(entry_price * 1.50, 2))
    option_tp2 = levels.get("option_take_profit_2", round(entry_price * 2.00, 2))

    risk_amount = round((entry_price - option_stop) * OPTION_MULTIPLIER, 2)
    potential_profit = round((option_tp2 - entry_price) * OPTION_MULTIPLIER, 2)
    risk_reward = round(potential_profit / risk_amount, 2) if risk_amount > 0 else 0

    distance_pct = round(abs(strike - price) / price * 100, 2) if price > 0 else 100

    score = 0

    if abs(delta) >= 0.75:
        score += 20
    elif abs(delta) >= 0.65:
        score += 16
    elif abs(delta) >= 0.55:
        score += 8
    else:
        score -= 25

    if distance_pct <= 3:
        score += 15
    elif distance_pct <= 6:
        score += 12
    elif distance_pct <= 8:
        score += 8
    elif distance_pct <= 12:
        score += 4
    else:
        score -= 30

    if volume >= 1000:
        score += 15
    elif volume >= 100:
        score += 10
    elif volume >= MIN_VOLUME:
        score += 5
    else:
        score -= 10

    if open_interest >= 3000:
        score += 15
    elif open_interest >= 1000:
        score += 12
    elif open_interest >= MIN_OPEN_INTEREST:
        score += 8
    else:
        score -= 12

    if spread_pct <= 3:
        score += 15
    elif spread_pct <= 6:
        score += 12
    elif spread_pct <= MAX_SPREAD_PCT:
        score += 6
    else:
        score -= 20

    if 45 <= dte <= 90:
        score += 10
    elif MIN_DTE <= dte <= MAX_DTE:
        score += 6
    else:
        score -= 10

    if 2 <= entry_price <= 20:
        score += 10
    elif 20 < entry_price <= MAX_ENTRY_PRICE:
        score += 5
    else:
        score -= 10

    if risk_amount <= MAX_RISK_PER_TRADE:
        score += 10
    else:
        score -= 15

    if risk_reward >= 3:
        score += 10
    elif risk_reward >= 2:
        score += 7
    elif risk_reward >= 1.5:
        score += 3
    else:
        score -= 10

    score = round(max(0, min(score, 100)), 2)

    recommendation, recommendation_reason = get_recommendation(
        score,
        delta,
        risk_reward,
        spread_pct,
        volume,
        open_interest,
    )

    return {
        "mid_price": round(entry_price, 2),
        "spread": spread,
        "spread_pct": spread_pct,
        "delta_estimate": delta,
        "delta": delta,
        "entry_price": round(entry_price, 2),
        "max_option_entry": levels.get("max_option_entry"),
        "stop_loss": option_stop,
        "take_profit": option_tp2,
        "take_profit_1": option_tp1,
        "take_profit_2": option_tp2,
        "trailing_stop": levels.get("option_trailing_stop"),
        "stock_entry_price": levels.get("stock_entry_price"),
        "stock_stop_loss": levels.get("stock_stop_loss"),
        "stock_take_profit_1": levels.get("stock_take_profit_1"),
        "stock_take_profit_2": levels.get("stock_take_profit_2"),
        "risk_amount": risk_amount,
        "potential_profit": potential_profit,
        "risk_reward": risk_reward,
        "strike_distance_pct": distance_pct,
        "contract_quality_score": score,
        "recommendation": recommendation,
        "recommendation_reason": recommendation_reason,
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
        if col not in contracts.columns:
            contracts[col] = 0
        contracts[col] = contracts[col].fillna(0)

    enriched_rows = []

    for _, row in contracts.iterrows():
        strike = safe_float(row.get("strike"))

        if not is_strike_valid(option_type, strike, price):
            continue

        score_data = score_contract(row, price, option_type)

        if abs(score_data.get("delta", 0)) < MIN_DELTA:
            continue

        if score_data.get("spread_pct", 100) > MAX_SPREAD_PCT:
            continue

        if safe_float(row.get("openInterest")) < MIN_OPEN_INTEREST:
            continue

        if safe_float(row.get("volume")) < MIN_VOLUME:
            continue

        if score_data.get("entry_price", 0) > MAX_ENTRY_PRICE:
            continue

        if score_data.get("risk_amount", 999999) > MAX_RISK_PER_TRADE:
            continue

        for key, value in score_data.items():
            row[key] = value

        enriched_rows.append(row)

    if not enriched_rows:
        return pd.DataFrame()

    candidates = pd.DataFrame(enriched_rows)

    candidates = candidates.sort_values(
        by=[
            "contract_quality_score",
            "delta",
            "risk_reward",
            "openInterest",
            "volume",
        ],
        ascending=False,
    )

    return candidates


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
                "No se encontró contrato válido. "
                "Se bloquearon contratos con delta bajo, strike muy lejano, "
                "spread alto, poco volumen o riesgo excesivo."
            )
            state["recommendation"] = "🔴 EVITAR"
            state["recommendation_reason"] = "No hay contrato institucional válido."
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
            "entry_price",
            "max_option_entry",
            "stop_loss",
            "take_profit",
            "take_profit_1",
            "take_profit_2",
            "trailing_stop",
            "stock_entry_price",
            "stock_stop_loss",
            "stock_take_profit_1",
            "stock_take_profit_2",
            "risk_amount",
            "potential_profit",
            "risk_reward",
            "strike_distance_pct",
            "contract_quality_score",
            "recommendation",
            "recommendation_reason",
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
        state["recommendation"] = "🔴 ERROR"
        state["recommendation_reason"] = str(e)
        return state