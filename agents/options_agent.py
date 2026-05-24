# agents/options_agent.py

ACCOUNT_SIZE = 10000
RISK_PERCENT = 0.02
MAX_CONTRACTS = 10


def options_agent(state):
    price = float(state.get("price", 0))
    trend = state.get("trend", "")
    risk = state.get("risk", "MEDIUM")
    rsi = float(state.get("rsi", 50))
    entry_ready = state.get("entry_ready", False)

    max_risk_allowed = ACCOUNT_SIZE * RISK_PERCENT

    strategy = "NO TRADE"
    strike = None
    dte = None
    confidence = 0
    reason = "No hay condición clara para operar opciones."

    option_price = 0
    contracts = 0
    max_loss = 0
    take_profit = 0
    stop_loss = 0
    trade_allowed = False

    if risk == "HIGH":
        reason = "Riesgo alto. Mejor no operar."

    elif trend == "UP" and rsi < 70:
        strategy = "WATCHLIST CALL"
        strike = round(price + 5, 2)
        dte = 30
        confidence = 65
        reason = "Tendencia alcista y RSI saludable."

        option_price = round(price * 0.03, 2)

        if entry_ready:
            strategy = "BUY CALL OPTION"
            confidence = 80
            reason = "Entrada CALL confirmada."

    elif trend == "DOWN" and rsi > 30:
        strategy = "WATCHLIST PUT"
        strike = round(price - 5, 2)
        dte = 30
        confidence = 65
        reason = "Tendencia bajista y RSI permite PUT."

        option_price = round(price * 0.03, 2)

        if entry_ready:
            strategy = "BUY PUT OPTION"
            confidence = 80
            reason = "Entrada PUT confirmada."

    if option_price > 0:
        cost_per_contract = option_price * 100
        contracts = int(max_risk_allowed // cost_per_contract)
        contracts = min(contracts, MAX_CONTRACTS)

        max_loss = round(cost_per_contract * contracts, 2)
        take_profit = round(option_price * 1.5, 2)
        stop_loss = round(option_price * 0.7, 2)

        if contracts > 0 and entry_ready:
            trade_allowed = True

    state["option_strategy"] = strategy
    state["option_reason"] = reason
    state["option_confidence"] = confidence
    state["strike"] = strike
    state["dte"] = dte
    state["option_price"] = option_price
    state["contracts"] = contracts
    state["max_loss"] = max_loss
    state["take_profit"] = take_profit
    state["stop_loss"] = stop_loss
    state["trade_allowed"] = trade_allowed

    return state